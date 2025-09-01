import mysql.connector
import pandas as pd

def fetch_data(query):
    """this function returns the result data of a query | query parameter required"""
    con = connect_db()
    try:
        cursor = con.cursor()
        cursor.execute(query)
        records = cursor.fetchall()
        return records
    except mysql.connector.Error as e:
        print("Error reading data from MySQL table", e)
    finally:
        if con.is_connected():
            con.close()
            
            
def connect_db():
	""" this function return the connection | host ,user,password and database this parameter required """
	connection = mysql.connector.connect(host="192.168.4.11",user="alkalyme",password="qazqwe@1234",database="stock_db")
	return connection
# print(connect_db())

def fetch_dataframe_from_speed(query): 
    """this function returns the result data of a query in a dataframe | query parameter required"""                        
    con = mysql.connector.connect(host="192.168.4.179",user="access_point_bse",password="Alk@506",database="bse_stocks_db") 
    try:                                                                                                                        
        df = pd.read_sql(query, con)                                                                                            
        return df                                                                                                          
    except mysql.connector.Error as e:                                                                                         
        print("Error reading data from MySQL table", e)                                                                     
    finally:                                                                                                                    
        if con.is_connected():                                                                                                      
            con.close() 

def fetch_dataframe(query):
    """this function returns the result data of a query in a dataframe | query parameter required"""
    con = connect_db()
    try:
        df = pd.read_sql(query, con)
        return df
    except mysql.connector.Error as e:
        print("Error reading data from MySQL table", e)
    finally:
        if con.is_connected():
            con.close()
            
# print (fetch_dataframe("select * from tick_nifty where date > '2024-10-25' ").to_csv('nifty_tick_2024-10-28_to_2024-10-29.csv'))


def query_execute_method(query_string, query_values):
    con = connect_db()
    try:
        cursor = con.cursor()
        cursor.execute(query_string, query_values)
        con.commit()
        print("✅ Data insert/update successful")
        return cursor.lastrowid
    except Exception as e:
        print("❌ Error executing query:", e)
    finally:
        if con.is_connected():
            con.close()
            
def single_execute_method(quary_string):
    con = connect_db()
    try:
        cursor = con.cursor()
        cursor.execute(quary_string)
        con.commit()
        print("DATA INSERT AND UPDATE SUCCESSFULLY")
        return cursor.lastrowid
    except Exception as e:
        print("Error reading data from MySQL table", e)
    finally:
        if con.is_connected():
            con.close()
            
            
def multiple_insert_data(sql, output_list):
    con = connect_db()
    try:
        cursor = con.cursor()
        cursor.executemany(sql, output_list)
        con.commit()
    except mysql.connector.Error as e:
        print("ERROR IN INSERTING DATA IN DATABASE", e)
    finally:
        if con.is_connected():
            con.close()
            
            
def multiple_insert_in_db(sql, output_list):
    con = connect_db()
    try:
        cursor = con.cursor()
        cursor.executemany(sql, output_list)
        con.commit()
        print ("DATA SUCCESSfully INSERTED")
    except mysql.connector.Error as e:
        print("ERROR IN INSERTING DATA IN DATABASE", e)
    finally:
        if con.is_connected():
            con.close()