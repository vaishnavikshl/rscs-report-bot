from flask import Flask, jsonify, request
from flask_httpauth import HTTPBasicAuth
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv
import os
from langchain_openai import OpenAI
from langchain_experimental.sql import SQLDatabaseChain
import ast
from loguru import logger
import threading
import sys 

load_dotenv()

# Remove the default logger handler
logger.remove()

# Add custom handlers for logging
logger.add("app.log", level="INFO", format="{time} {level} {message}")
logger.add(sys.stdout, level="INFO", format="{time} {level} {message}")


app = Flask(__name__)
CORS(app)
auth = HTTPBasicAuth()

users = {
    "john doe": "john@12345"
}

@auth.verify_password
def verify_password(username, password):
    if username in users and password == users[username]:
        logger.info(f"User {username} authenticated successfully.")
        return True
    logger.warning(f"Failed authentication attempt for user {username}.")
    return False

@auth.error_handler
def auth_error(status):
    logger.warning("Unauthorized access attempt.")
    return jsonify({'message': 'Unauthorized Access'}), 401

SERVER = os.getenv('SERVER')
DATABASE = os.getenv('DATABASE')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
API_KEY = os.getenv('OPENAI_API_KEY')
include_tables_str = os.getenv('INCLUDE_TABLES')
INCLUDE_TABLES = ast.literal_eval(include_tables_str) if include_tables_str else []
openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION')
azure_deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME')

if not all([SERVER, DATABASE, USERNAME, PASSWORD, API_KEY]):
    logger.warning("Missing required environment variables.")
    raise ValueError("Please set all environment variables: SERVER, DATABASE, USERNAME, PASSWORD, API_KEY")

url = f"mssql+pyodbc:///?odbc_connect=Driver={{ODBC Driver 17 for SQL Server}};Server=tcp:{SERVER},1433;Database={DATABASE};Uid={USERNAME};Pwd={PASSWORD};MARS_Connection=Yes;"
url += "Connection Timeout=30;"

llm = OpenAI(openai_api_key=API_KEY)
PROMPT = """
The question: {question}
"""

PROMPT1 = """
- Return only 10 rows if the user doesn't specify the row count.
- Retrieve only distinct results.
- Inform the user if all records cannot be displayed upon request.
- Indicate that details are null or unavailable if the query returns no records.
- Do not provide an answer if the question is unrelated to the database.
- If the column name is not specified in the question, use the last value in the question as the asset item or name.
- If there is confusion in selecting which column to choose in the WHERE clause, select all related columns based on the values given in the question's context.
- This is the test sql query and user question.
- Assets and Locations are the main columns to query.
- The Question :- what is the Manufacturer of the Deep Fryer
- The SQL Query :-  SELECT DISTINCT [Manufacturer]
                    FROM [MyAiView]
                    WHERE [Assets] LIKE '%Deep Fryer%'
                    OR [CategoryName] LIKE '%Fryer%'
                    OR [Manufacturer] LIKE '%Antunes%'
                    OR [ModelNo.] LIKE '%G12001%'
                    OR [Model#] LIKE '%G12001%'  
                    OR [Model Number] LIKE '%G12001%'
                    OR [Endoflife] LIKE '%2022-04-04%'
                    ORDER BY [Manufacturer] DESC
                    OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY;

The question: {question}
The error: {error}
"""

try:
    logger.info("Attempting to create database engine.")
    engine = create_engine(url, pool_size=20, max_overflow=0)
    logger.info("Database engine created successfully.")
except SQLAlchemyError as e:
    logger.critical(f"Error creating database engine: {e}", exc_info=True)
    raise

try:
    logger.info("Attempting to create SQLDatabase instance.")
    db = SQLDatabase(engine, view_support=True, indexes_in_table_info=True, include_tables=['MyAiView'])
    logger.info("SQLDatabase instance created successfully.")
except Exception as e:
    logger.critical(f"Error creating SQLDatabase instance: {e}", exc_info=True)
    raise

db_chain = SQLDatabaseChain.from_llm(llm=llm, use_query_checker=True, db=db, return_sql=False, return_intermediate_steps=False, verbose=True)

def process_user_query(user_query, results_container):
    try:
        logger.info(f"Processing user query: {user_query}")
        results = db_chain.invoke(PROMPT.format(question=user_query))
        logger.info("Query processed successfully.")
        results_container.append({"response": results['result']})
    except Exception as error:
        logger.warning(f"Error processing query: {error}")
        try:
            error = str(error).split('\n')[0]
            results = db_chain.invoke(PROMPT1.format(question=user_query, error=error))
            logger.info("Processed query with error handling.")
            results_container.append({"response": results['result']})
        except Exception as e:
            logger.warning(f"Critical error: {e}")
            results_container.append({'message': 'I dont understand your question please provide more details.', 'error': str(e)})

@app.route('/v1/sql', methods=['POST'])
@auth.login_required
def user_query():
    try:
        user_query = request.form.get("user_query")
        if not user_query:
            logger.warning("User query not provided.")
            return jsonify({'message': 'Please provide a question in the question field.'}), 400

        results_container = []
        user_thread = threading.Thread(target=process_user_query, args=(user_query, results_container))
        user_thread.start()
        user_thread.join()  
        
        return jsonify(results_container[0]), 200

    except Exception as e:
        logger.warning(f"Error starting thread: {e}")
        return jsonify({'message': 'Internal server error.'}), 500

if __name__ == '__main__':
    logger.info("Starting Flask application.")
    app.run(debug=True, threaded=True)





































# from flask import Flask, jsonify, request
# from flask_httpauth import HTTPBasicAuth
# from flask_cors import CORS
# from sqlalchemy import create_engine
# from langchain_community.utilities import SQLDatabase
# from dotenv import load_dotenv
# import os
# from langchain_openai import AzureChatOpenAI, OpenAI
# from langchain_experimental.sql import SQLDatabaseChain
# import ast
# import logging
# from langchain.prompts.prompt import PromptTemplate

# load_dotenv()

# logging.basicConfig(level=logging.INFO,  
#                     format='%(asctime)s %(levelname)s %(message)s',  
#                     handlers=[
#                         logging.FileHandler("app.log"), 
#                         logging.StreamHandler() 
#                     ])

# app = Flask(__name__)
# CORS(app)
# auth = HTTPBasicAuth()

# users = {
#     "john doe": "john@12345"
# }

# @auth.verify_password
# def verify_password(username, password):
#     if username in users and password == users[username]:
#         logging.info(f"User {username} authenticated successfully.")
#         return True
#     logging.warning(f"Failed authentication attempt for user {username}.")
#     return False

# @auth.error_handler
# def auth_error(status):
#     logging.warning("Unauthorized access attempt.")
#     return jsonify({'message': 'Unauthorized Access'}), 401

# # Load environment variables
# SERVER = os.getenv('SERVER')
# DATABASE = os.getenv('DATABASE')
# USERNAME = os.getenv('USERNAME')
# PASSWORD = os.getenv('PASSWORD')
# SCHEMA_NAME = os.getenv('SCHEMA_NAME')
# API_KEY = os.getenv('OPENAI_API_KEY')
# include_tables_str = os.getenv('INCLUDE_TABLES')
# INCLUDE_TABLES = ast.literal_eval(include_tables_str) if include_tables_str else []
# openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION')
# azure_deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME')

# if not all([SERVER, DATABASE, USERNAME, PASSWORD, API_KEY]):
#     logging.warning("Missing required environment variables.")
#     raise ValueError("Please set all environment variables: SERVER, DATABASE, USERNAME, PASSWORD, API_KEY")

# url = f"mssql+pyodbc:///?odbc_connect=Driver={{ODBC Driver 17 for SQL Server}};Server=tcp:{SERVER},1433;Database={DATABASE};Uid={USERNAME};Pwd={PASSWORD};MARS_Connection=Yes;"

# llm = OpenAI(openai_api_key="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", temperature=0)

# PROMPT = """
# Upon receiving a question, understand the user's intent. Generate and execute a syntactically correct MS SQL Server query based on asset items, names, and related columns. Review the results and provide a detailed answer.

# - Return only 10 rows if the user doesn't specify the row count.
# - Retrieve only distinct results.
# - Inform the user if all records cannot be displayed upon request.
# - Indicate that details are null or unavailable if the query returns no records.
# - Do not provide an answer if the question is unrelated to the database.
# - If the column name is not specified in the question, use the last value in the question as the asset item or name.
# - If there is confusion in selecting which column to choose in the WHERE clause, select all related columns based on the values given in the question's context.
# - This is the test sql query and user question.
# - Assets and Locations are the main columns to query.
# - The Question :- what is the Manufacturer of the Deep Fryer
# - The SQL Query :-  SELECT DISTINCT [Manufacturer]
#                     FROM [MyAiView]
#                     WHERE [Assets] LIKE '%Deep Fryer%'
#                     OR [CategoryName] LIKE '%Fryer%'
#                     OR [Manufacturer] LIKE '%Antunes%'
#                     OR [ModelNo.] LIKE '%G12001%'
#                     OR [Model#] LIKE '%G12001%'  
#                     OR [Model Number] LIKE '%G12001%'
#                     OR [Endoflife] LIKE '%2022-04-04%'
#                     ORDER BY [Manufacturer] DESC
#                     OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY;

# The question: {question}
# """

# PROMPT1 = """
# Upon receiving a question, understand the user's intent. Generate and execute a syntactically correct MS SQL Server query based on asset items, names, and related columns. Review the results and provide a detailed answer.

# - Return only 10 rows if the user doesn't specify the row count.
# - Retrieve only distinct results.
# - Inform the user if all records cannot be displayed upon request.
# - Indicate that details are null or unavailable if the query returns no records.
# - Do not provide an answer if the question is unrelated to the database.
# - If the column name is not specified in the question, use the last value in the question as the asset item or name.
# - If there is confusion in selecting which column to choose in the WHERE clause, select all related columns based on the values given in the question's context.
# - This is the test sql query and user question.
# - Assets and Locations are the main columns to query.
# - The Question :- what is the Manufacturer of the Deep Fryer
# - The SQL Query :-  SELECT DISTINCT [Manufacturer]
#                     FROM [MyAiView]
#                     WHERE [Assets] LIKE '%Deep Fryer%'
#                     OR [CategoryName] LIKE '%Fryer%'  
#                     OR [SerialNumber] LIKE '%Llojdh1746%'
#                     OR [Manufacturer] LIKE '%Antunes%'
#                     OR [Model#] LIKE '%G12001%'
#                     OR [Model Number] LIKE '%G12001%'
#                     OR [Endoflife] LIKE '%2022-04-04%'
#                     ORDER BY [Manufacturer] DESC
#                     OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY;

# The question: {question}
# The error: {error}
# """

# engine = create_engine(url, pool_size=20, max_overflow=0)


# db = SQLDatabase(engine, view_support=True, indexes_in_table_info=True, include_tables=['MyAiView'])

# db_chain = SQLDatabaseChain.from_llm(llm=llm, use_query_checker=True, db=db, return_sql=False, return_intermediate_steps=False, verbose=True, top_k=10)

# @app.route('/v1/sql', methods=['POST'])
# @auth.login_required
# def user_query():
#     try:
#         user_query = request.form.get("user_query")
#         if not user_query:
#             logging.warning("User query not provided.")
#             return jsonify({'message': 'Please provide a question in the question field.'}), 400

#         logging.info(f"Received user query: {user_query}")
#         results = db_chain.invoke(PROMPT.format(question=user_query))
#         logging.info("Query processed successfully.")

#         return jsonify({"response": results['result']}), 200

#     except Exception as error:
#         logging.warning(f"Error processing query: {error}")
#         try:
#             error = str(error).split('\n')[0]
#             results = db_chain.invoke(PROMPT1.format(question=user_query, error=error))
#             logging.info("Processed query with error handling.")
#             return jsonify({"response": results['result']}), 200

#         except Exception as e:
#             logging.warning(f"Critical error: {e}")
#             return jsonify({'message': 'I dont understand your question please provide more details.', 'error': str(e)}), 500

# if __name__ == '__main__':
#     logging.info("Starting Flask application.")
#     app.run(debug=True, threaded=True)






























# from flask import Flask, jsonify, request
# from flask_httpauth import HTTPBasicAuth
# from flask_cors import CORS
# from sqlalchemy import create_engine
# from langchain_community.utilities import SQLDatabase
# from dotenv import load_dotenv
# import os
# from langchain_openai import AzureChatOpenAI
# from langchain_openai import OpenAI
# from langchain_experimental.sql import SQLDatabaseChain
# import ast
# import logging
# from langchain.prompts.prompt import PromptTemplate
 
# load_dotenv()
 

# logging.basicConfig(level=logging.INFO,  
#                     format='%(asctime)s %(levelname)s %(message)s',  
#                     handlers=[
#                         logging.FileHandler("app.log"), 
#                         logging.StreamHandler() 
#                     ])
 
# app = Flask(__name__)
# CORS(app)
# auth = HTTPBasicAuth()
 
# users = {
#     "john doe": "john@12345"
# }
 
# @auth.verify_password
# def verify_password(username, password):
#     if username in users and password == users[username]:
#         logging.info(f"User {username} authenticated successfully.")
#         return True
#     logging.warning(f"Failed authentication attempt for user {username}.")
#     return False
 
# @auth.error_handler
# def auth_error(status):
#     logging.warning("Unauthorized access attempt.")
#     return jsonify({'message': 'Unauthorized Access'}), 401
 
# SERVER = os.getenv('SERVER')
# DATABASE = os.getenv('DATABASE')
# USERNAME = os.getenv('USERNAME')
# PASSWORD = os.getenv('PASSWORD')
# SCHEMA_NAME = os.getenv('SCHEMA_NAME')
# API_KEY = os.getenv('OPENAI_API_KEY')
# include_tables_str = os.getenv('INCLUDE_TABLES')
# INCLUDE_TABLES = ast.literal_eval(include_tables_str) if include_tables_str else []
# openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION')
# azure_deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME')
 
# if not all([SERVER, DATABASE, USERNAME, PASSWORD, API_KEY]):
#     logging.warning("Missing required environment variables.")
#     raise ValueError("Please set all environment variables: SERVER, DATABASE, USERNAME, PASSWORD, API_KEY")
 
# url = f"mssql+pyodbc:///?odbc_connect=Driver={{ODBC Driver 17 for SQL Server}};Server=tcp:{SERVER},1433;Database={DATABASE};Uid={USERNAME};Pwd={PASSWORD};MARS_Connection=Yes;"
# # llm = AzureChatOpenAI(
# #     openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
# #     azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
# # )
 
# llm = OpenAI(openai_api_key="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")
 
# PROMPT = """
# Upon receiving a question, understand the user's intent. Generate and execute a syntactically correct MS SQL Server query based on asset items, names, and related columns. Review the results and provide a detailed answer.
 
# - Return only 10 rows if the user doesn't specify the row count.
# - Retrieve only distinct results.
# - Inform the user if all records cannot be displayed upon request.
# - Indicate that details are null or unavailable if the query returns no records.
# - Do not provide an answer if the question is unrelated to the database.
# - If the column name is not specified in the question, use the last value in the question as the asset item or name.
# - If there is confusion in selecting which column to choose in the WHERE clause, select all related columns based on the values given in the question's context.
# - This is the test sql query and user question.
# - Assets and Locations are the main columns to query.
# - The Question :- what is the Manufacturer of the Deep Fryer
# - The SQL Query :-  SELECT DISTINCT [Manufacturer]
#                     FROM [MyAiView]
#                     WHERE [Assets] LIKE '%Deep Fryer%'
#                     OR [SerialNumber] LIKE '%Lojdh1746%'
#                     OR [CategoryName] LIKE '%Fryer%'
#                     OR [Manufacturer] LIKE '%Antunes%'
#                     OR [ModelNo.] LIKE '%G12001%'
#                     OR [Model#] LIKE '%G12001%'  
#                     OR [Model Number] LIKE '%G12001%'
#                     ORDER BY [Manufacturer] DESC
#                     OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY;
 
# The question: {question}
# """
 
# PROMPT1 = """
# Upon receiving a question, understand the user's intent. Generate and execute a syntactically correct MS SQL Server query based on asset items, names, and related columns. Review the results and provide a detailed answer.
 
# - Return only 10 rows if the user doesn't specify the row count.
# - Retrieve only distinct results.
# - Inform the user if all records cannot be displayed upon request.
# - Indicate that details are null or unavailable if the query returns no records.
# - Do not provide an answer if the question is unrelated to the database.
# - If the column name is not specified in the question, use the last value in the question as the asset item or name.
# - If there is confusion in selecting which column to choose in the WHERE clause, select all related columns based on the values given in the question's context.
# - This is the test sql query and user question.
# - Assets and Locations are the main columns to query.
# - The Question :- what is the Manufacturer of the Deep Fryer
# - The SQL Query :-  SELECT DISTINCT [Manufacturer]
#                     FROM [MyAiView]
#                     WHERE [Assets] LIKE '%Deep Fryer%' 
#                     OR [SerialNumber] LIKE '%Lojdh1746% 
#                     OR [CategoryName] LIKE '%Fryer%'
#                     OR [Manufacturer] LIKE '%Antunes%'
#                     OR [Model#] LIKE '%G12001%'
#                     OR [Model Number] LIKE '%G12001%'
#                     ORDER BY [Manufacturer] DESC
#                     OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY;
 
# The question: {question}
# The error: {error}
# """
 
# engine = create_engine(url,pool_size=20, max_overflow=0)
 
# db = SQLDatabase(engine, view_support=True,indexes_in_table_info=True, include_tables=['MyAiView'])
 
# db_chain = SQLDatabaseChain.from_llm(llm=llm, use_query_checker=True, db=db,return_sql=False,return_intermediate_steps=False, verbose=True, top_k=10)
 
# @app.route('/v1/sql', methods=['POST'])
# @auth.login_required
# def user_query():
#     try:
#         user_query = request.form.get("user_query")
#         if not user_query:
#             logging.warning("User query not provided.")
#             return jsonify({'message': 'Please provide a question in the question field.'}), 400
       
#         logging.info(f"Received user query: {user_query}")
#         results = db_chain.invoke(PROMPT.format(question=user_query))
#         logging.info("Query processed successfully.")
       
#         return jsonify({"response": results['result']}), 200
   
#     except Exception as error:
#         logging.warning(f"Error processing query: {error}")
#         try:
#             error = str(error).split('\n')[0]
#             results = db_chain.invoke(PROMPT1.format(question=user_query, error=error))
#             logging.info("Processed query with error handling.")
#             return jsonify({"response": results['result']}), 200
           
#         except Exception as e:
#             logging.warning(f"Critical error: {e}")
#             return jsonify({'message': 'I dont understand your question please provide more details.', 'error': str(e)}), 500
 
# if __name__ == '__main__':
#     logging.info("Starting Flask application.")
#     app.run(debug=True, threaded=True)