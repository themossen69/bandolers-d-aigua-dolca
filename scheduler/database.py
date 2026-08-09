"""
Aquest fitxer fa les consultes a la base de dades.
"""

import sqlite3
import sys
import os
from pandas import read_csv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from functions import execute_db

private_path = os.path.abspath(os.path.join(os.getcwd(), "..", "_private"))
if private_path not in sys.path:
    sys.path.insert(0, private_path)
from constants import DB

# obtenir inici controls
def get_inici_controls(cursor: sqlite3.Cursor) -> list[tuple[str, str]]:
    """
    Retorna una llista amb la data d'inici de tots els controls
    """
    cursor.execute("SELECT id, inici FROM controls ORDER BY inici")
    result = cursor.fetchall()
    return [(f"inici_control_{row[0]}", row[1]) for row in result] if result else []

def get_final_controls(cursor: sqlite3.Cursor) -> list[tuple[str, str]]:
    """
    Retorna una llista amb la data de finalització de tots els controls
    """
    cursor.execute("SELECT id, final FROM controls ORDER BY final")
    result = cursor.fetchall()
    return [(f"final_control_{row[0]}", row[1]) for row in result] if result else []

def get_bandolers(cursor: sqlite3.Cursor) -> list[int]:
    """
    Retorna una llista amb els IDs d'usuari de tots els usuaris
    """
    cursor.execute("SELECT id FROM bandolers WHERE estat = 'jugant'")
    result = cursor.fetchall()
    return [row[0] for row in result] if result else []

def get_last_day_control(cursor: sqlite3.Cursor, dia: int) -> str:
    """
    Retorna l'id de l'últim control assignat al dia especificat.
    """
    cursor.execute("SELECT id FROM controls WHERE dia = ? ORDER BY inici DESC LIMIT 1", (dia,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0

def get_final_date_control(cursor: sqlite3.Cursor, control_id: str) -> str:
    """
    Retorna la data de finalització del control especificat.
    """
    cursor.execute("SELECT final FROM controls WHERE id = ?", (control_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else None

def get_start_date_control(cursor: sqlite3.Cursor, control_id: str) -> str:
    """
    Retorna la data d'inici del control especificat.
    """
    cursor.execute("SELECT inici FROM controls WHERE id = ?", (control_id,))
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else None

def is_it_the_last_control_of_the_day(cursor: sqlite3.Cursor, control_id: str) -> bool:
    """
    Retorna True si el control especificat és l'últim control del dia, False en cas contrari.
    """
    cursor.execute("SELECT dia FROM controls WHERE id = ?", (control_id,))
    result = cursor.fetchone()
    if result and result[0] is not None:
        dia = result[0]
        last_control_id = get_last_day_control(cursor, dia)
        return control_id == last_control_id
    return False

def get_tasks(filename: str) -> list[tuple[int, str, str]]:
    """
    Retorna una llista amb les tasques programades a la base de dades.
    """
    # add control tasks to scheduler table
    controls = execute_db(get_inici_controls)
    controls.extend(execute_db(get_final_controls))

    tasks = []
    i=0
    for control in controls:
        task_name, scheduled_time = control
        tasks.append((i, task_name, scheduled_time))
        i+=1

    # add start and end tasks to scheduler table
    lines = read_csv(filename)
    for index, row in lines.iterrows():
        task_name = row['id']
        scheduled_time = row['time']
        tasks.append((i, task_name, scheduled_time))
        i+=1
    return tasks
