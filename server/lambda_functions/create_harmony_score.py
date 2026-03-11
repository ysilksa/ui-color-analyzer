#
# Given an image ID, the image will be retrieved, and its harmony score will be calcuated from the palette given. 
# If the image has no palette yet, a client error is returned and the user is told to generate the palette first. 
#

import os
import pymysql
import json
import colorsys 
import logging 
from tenacity import retry, stop_after_attempt, wait_exponential

#
# helper for opening DB connection, retrieve from lambda function env variables 
#
def get_dbConn():
    conn = pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        autocommit=False
    )

    return conn

#
# helper for retrieving palette based on image ID
#
def get_palette(image_id, dbCursor):
    sql = """
    SELECT palette FROM images WHERE image_id = %s;
    """

    dbCursor.execute(sql, [image_id])
    row = dbCursor.fetchone()

    if not row: 
        raise ValueError("no such image ID")
    if row[0] == None:
        raise ValueError("please generate the palette for this image first!")
    
    return json.loads(row[0])

# 
# helper for turning RGB colors to HSB
# 
def rgb_to_hues(palette):
    hues = []

    for r, g, b in palette:
        r /= 255
        g /= 255
        b /= 255

        h, s, v = colorsys.rgb_to_hsv(r, g, b)

        hues.append(h * 360)

    return hues

# 
# helper to calculate distance between 2 given hues
#
def calculate_hue_distance(h1, h2):
    diff = abs(h1 - h2)
    return min(diff, 360 - diff)


#
# helper to compute harmony given a color palette (in hues)
#
def compute_harmony(hues):
    score = 0 
    comparisons = 0 
    hues_len = len(hues)

    for i in range(hues_len):
        for j in range(i + 1, hues_len):
            distance = calculate_hue_distance(hues[i], hues[j])
            comparisons += 1

            # add to score if complementary colors
            if 150 <= distance <= 210:
                score += 1

            # add to score if analogous colors
            elif distance <= 30:
                score += 0.5

            # add to score if triadic colors
            elif 100 <= distance <= 140:
                score += 0.8
    
    # get the avg 
    if comparisons > 0:
        score = score / comparisons
    
    return score 

#
# store the harmony score
#
def store_harmony_score(image_id, score, dbCursor):

    sql = """
    UPDATE images
    SET harmony_score = %s
    WHERE image_id = %s;
    """

    dbCursor.execute(sql, [score, image_id])    

#
# handles all the main logic in one function 
#
@retry (
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True      
)
def create_harmony_score(image_id):
    try:
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()
        dbConn.begin()

        palette = get_palette(image_id, dbCursor)
        hues = rgb_to_hues(palette)
        score = compute_harmony(hues)
        store_harmony_score(image_id, score, dbCursor)

        dbConn.commit()

        return score
    except Exception as err:
        try:
            dbConn.rollback()
        except: 
            pass
        logging.error("error in create_harmony_score")
        logging.error(str(err))
        raise
    finally:
        try:
            dbConn.close()
        except:
            pass

        try:
            dbCursor.close()
        except:
            pass


def lambda_handler(event, context):
    try:
        image_id = event['image_id']

        score = create_harmony_score(image_id)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "image_id": image_id,
                "harmony_score": score
            })
        }
    except ValueError as err:

        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(err)})
        }
    except Exception:

        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal server error"})
        } 

