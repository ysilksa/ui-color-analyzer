import pymysql
import json
import os 
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
# calculate relative luminance (used AI to help find equations for this)
#
def channel_transform(c):
    c = c / 255
    if c <= 0.03928:
        return c / 12.92
    else:
        return ((c + 0.055) / 1.055) ** 2.4

def compute_luminance(rgb):
    r, g, b = rgb
    r = channel_transform(r)
    g = channel_transform(g)
    b = channel_transform(b)

    luminance = 0.2176 * r + 0.7152 * g + 0.0722 * b 
    return luminance

#
# calculate the contrast ratio
#
def contrast_ratio(l1, l2):
    L1 = max(l1, l2)
    L2 = min(l1, l2)
    return (L1 + 0.05) / (L2 + 0.05)

#
# helpers for computing and storing the contrast score
#
def compute_contrast_score(palette):
    luminances = [compute_luminance(color) for color in palette]
    ratios = []
    len_luminances = len(luminances)

    for i in range(len_luminances):
        for j in range(i + 1, len_luminances):
            ratio = contrast_ratio(luminances[i], luminances[j])
            ratios.append(ratio)

    # count the number of WCAG complaint counts
    passing = 0 
    for r in ratios:
        if r >= 4.5: # threshold for the WCAG AA text contrast
            passing += 1
        
    if len(ratios) == 0:
        return 0 

    return passing / len(ratios)

def store_contrast_score(image_id, score, dbCursor):

    sql = """
    UPDATE images
    SET contrast_score = %s
    WHERE image_id = %s;
    """

    dbCursor.execute(sql, [score, image_id])

#
# helper with main logic
#
@retry (
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True      
)
def create_contrast_score(image_id):
    try:
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()
        dbConn.begin()

        palette = get_palette(image_id, dbCursor)
        score = compute_contrast_score(palette)
        store_contrast_score(image_id, score, dbCursor)

        dbConn.commit()
        return score
    except Exception as err:
        try:
            if dbConn:
                dbConn.rollback()
        except:
            pass

        logging.error("error in create_contrast_score")
        logging.error(str(err))
        raise
    finally:
        try:
            if dbCursor:
                dbCursor.close()
        except:
            pass

        try:
            if dbConn:
                dbConn.close()
        except:
            pass

#
# overall lambda handler
#
def lambda_handler(event, context):
    try:
        image_id = event['image_id']
        score = create_contrast_score(image_id)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "image_id": image_id,
                "contrast_score": score
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