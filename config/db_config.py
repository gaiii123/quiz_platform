
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import threading
import time
from pymongo.errors import ConnectionFailure
# MongoDB connection
client1 = MongoClient("mongodb+srv://798white:daDd4Utd0q5DyTKx@cluster0.wc8bf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0", server_api=ServerApi('1'))
client2 = MongoClient("mongodb+srv://gaiii123:2001%40Gayan@cluster0.8ezvo.mongodb.net/", server_api=ServerApi('1'))

db1 = client1["quiz_platform"]
db2 = client2["quiz_platform"]

users_collection1 = db1["users"]
quizzes_collection1 = db1["quizzes"]
results_collection1 = db1["results"]

users_collection2 = db2["users"]
quizzes_collection2 = db2["quizzes"]
results_collection2 = db2["results"]

def sync_databases():
    while True:
        try:
            # Sync users collection
            users_data = list(users_collection1.find())
            users_collection2.delete_many({})
            if users_data:
                users_collection2.insert_many(users_data)

            # Sync quizzes collection
            quizzes_data = list(quizzes_collection1.find())
            quizzes_collection2.delete_many({})
            if quizzes_data:
                quizzes_collection2.insert_many(quizzes_data)

            # Sync results collection
            results_data = list(results_collection1.find())
            results_collection2.delete_many({})
            if results_data:
                results_collection2.insert_many(results_data)

            print("Databases synchronized successfully.")
        except ConnectionFailure as e:
            print(f"Connection failed: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

        time.sleep(3600)  # Sync every hour

# Start the synchronization in a separate thread
sync_thread = threading.Thread(target=sync_databases)
sync_thread.daemon = True
sync_thread.start()

def get_collection(collection1, collection2):
    try:
        # Try to use the first cluster
        collection1.find_one()
        return collection1
    except ConnectionFailure:
        # If the first cluster fails, use the second cluster
        return collection2

# Usage example
users_collection = get_collection(users_collection1, users_collection2)
quizzes_collection = get_collection(quizzes_collection1, quizzes_collection2)
results_collection = get_collection(results_collection1, results_collection2)
