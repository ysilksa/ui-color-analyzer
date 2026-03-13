# UI Color Analyzer 
Created by: Isabella Yan
For use in CS 310 Project

## Project Installation and Running Client UI
1. Clone or download project files.
2. Locate the client directory from the root directory of this project. 
3. Within the client directory, create a Python environment.
4. Install dependencies from 'requirements.txt' in the client directory. 
5. Within the client directory, run: 'python client.py'

Note that this project uses serverless architecture, such that no external server setup is needed. 

It is also important that one limitation of this project is that it currently only accepts image/jpeg files. Please keep this mind when you upload images to the application. 

## Database Setup
The database schema is provided in '/database/schema.sql' from the root directory of this project. Running this file on a PostgreSQL database will create the table needed for this project. 

## API Endpoint
The base URL of the API is: https://rglmi1s1v8.execute-api.us-east-2.amazonaws.com

The main endpoints are:
- POST /images
Uploads an image and returns a generated image ID.

- GET /images/{image_id}
Given an image ID, returns its palette, harmony score, and contrast score.

- GET /images/search?score_type=&threshold=
Given a score type (harmony/contrast) and a threshold, returns all images with scores above a specified threshold.

## Server Code
Given that the architecture of this project is serverless, the exact lambda functions used in AWS Lambda are under '/server/lambda_functions/' from the root directory of this project. 