import weaviate
import openai
import requests
import json
import os
import asyncio
import weaviate
import weaviate.classes as wvc
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter

load_dotenv()

print(os.getcwd())

with open ("output.json", "r") as f:
    json_data = json.load(f)

# Weaviate client
api_key = os.getenv("OPENAI_API_KEY")
client = weaviate.connect_to_local(
            headers={
                "X-OpenAI-Api-Key": api_key
            }
        )

def create_schema():
    webScrapeSchema = client.collections.create(
                name = "webScrapeSchema",
                description = "A class to store information regarding web scraping",
                properties = [
                    wvc.config.Property(
                        name="title",
                        data_type=wvc.config.DataType.TEXT,
                        description="This stores the title of a webpage",
                    ), 
                    wvc.config.Property(
                        name="chunk",
                        data_type=wvc.config.DataType.TEXT,
                        description="This is a chunk of text extracted from a webpage",
                    ), 
                ],
            )

def chunk_text(text):
    splitter = RecursiveCharacterTextSplitter(chunk_size=400, overlap_size=100)
    chunks = splitter.split(text)
    return chunks

def store_data(jsonData):
    for data in jsonData:
        title = data["title"]
        content = data["content"]
        chunks = chunk_text(content)
        for chunk in chunks:
            client.data_object.create(
                class_name="webScrapeSchema",
                properties={
                    "title": title,
                    "chunk": chunk
                }
            )