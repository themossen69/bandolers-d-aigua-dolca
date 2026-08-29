import sqlite3
import io
import random
import os
import queue
import sys
import csv
import time
from functools import wraps
import traceback
from datetime import date

private_path = os.path.abspath(os.path.join(os.getcwd(), "..", "_private"))
if private_path not in sys.path:
    sys.path.insert(0, private_path)

from constants import ADMIN_ID, DB, QUEUE
from const import BANDOLER_FIELD_NAMES

def telegram_safe(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            print(f"Error en executar {func.__name__}")
            traceback.print_exc()
    return wrapper

###### funcions de gestió de la base de dades ######

def create_DB(cursor) -> None:
    # Crear la taula "bandolers" amb relació recursiva
    # cursor.execute("DROP TABLE IF EXISTS bandolers")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bandolers (
        id INTEGER PRIMARY KEY,
        nom TEXT NOT NULL,
        sobrenom TEXT,
        descripcio TEXT,
        estat TEXT CHECK (estat IN ('jugant', 'mort', 'pendent')),
        foto BLOB,
        kills INTEGER DEFAULT 0,
        victima INTEGER,
        punts INTEGER DEFAULT 0,
        permis_instagram BOOLEAN DEFAULT 0,
        FOREIGN KEY (victima) REFERENCES bandolers (id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
                   CREATE INDEX IF NOT EXISTS idx_kills ON bandolers(kills)
    """)
    cursor.execute("""
                   CREATE INDEX IF NOT EXISTS idx_estat ON bandolers(estat)
    """)

# Crear taula variables
def create_var_DB(cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS variables (
        nom TEXT PRIMARY KEY,
        valor TEXT
    )
    """)
    cursor.execute("""
                   INSERT OR IGNORE INTO variables (nom, valor) VALUES ('inscripcio_disponible', 'True')
    """)
    cursor.execute("""
                   INSERT OR IGNORE INTO variables (nom, valor) VALUES ('guanyador', '0')
    """)

def create_controls_DB(cursor, csv_file: str) -> None:
    # cursor.execute("DROP TABLE IF EXISTS controls")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS controls (
            id TEXT PRIMARY KEY,
            inici TEXT,
            final TEXT,
            dia integer
        )
        """)
    with open(csv_file, 'r', encoding='utf-8') as f:
        lector_csv = csv.reader(f)
        for i, row in enumerate(lector_csv):
            if i == 0:
                continue  # Saltar capçalera
            control_id, inici, final = row
            dia, _, _, _, _, _ = data_strip(inici)
            cursor.execute("INSERT OR IGNORE INTO controls (id, inici, final, dia) VALUES (?, ?, ?, ?)", (control_id, inici, final, dia))

def create_controls_bandolers_DB(cursor) -> None:
    # cursor.execute("DROP TABLE IF EXISTS controls_bandolers")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS controls_bandolers (
        id_control TEXT,
        id_bandoler INTEGER,
        timestamp TEXT,
        PRIMARY KEY (id_control, id_bandoler),
        FOREIGN KEY (id_control) REFERENCES controls(id) ON DELETE SET NULL,
        FOREIGN KEY (id_bandoler) REFERENCES bandolers(id) ON DELETE SET NULL
    )
    """)

def restart_db(cursor: sqlite3.Cursor) -> None:
    cursor.execute("DROP TABLE IF EXISTS bandolers")
    cursor.execute("DROP TABLE IF EXISTS controls")
    cursor.execute("DROP TABLE IF EXISTS controls_bandolers")
    cursor.connection.commit()
    create_DB(cursor)  # Re-crea la base de dades després de reiniciar
    print("Base de dades reiniciada.")

def change_inscripcio_disponible(cursor: sqlite3.Cursor) -> None:
    valor = get_inscripcio_disponible(cursor)
    cursor.execute("UPDATE variables SET valor=? WHERE nom='inscripcio_disponible'", (str(not valor),))

def execute_db(func, *args: tuple, timeout=15):
    results_queue = queue.Queue() # Crea una cua per emmagatzemar els resultats
    QUEUE.put((func, args, results_queue))  # Afegeix la funció i els arguments a la cua
    try:
        result = results_queue.get(timeout=timeout)  # Espera i retorna el resultat de la funció
        if isinstance(result, Exception):
            raise result  # Si el resultat és una excepció, la llencem
        return result
    
    except queue.Empty:
        print(f"Timeout: La funció {func.__name__} ha trigat més de {timeout}s.")
        return None

def db_worker():
    try:
        conn = sqlite3.connect(get_path_db(), check_same_thread=False, timeout=10) # TODO: troban nº adequat
        cursor = conn.cursor()

        create_DB(cursor)  # Assegura que la base de dades està creada abans de començar a processar esdeveniments
        conn.commit()

    except Exception as e:
        print(f"Error a l'iniciar el Worker de BD: {e}")
        return
    
    while True:
        task = QUEUE.get()
        func, args, results_queue = task
        if func is None:  # Si la funció és None, sortim del bucle
            QUEUE.task_done()
            break
        try:
            result = func(cursor, *args)  # Executa la funció amb el cursor i els arguments
            conn.commit()  # Commit els canvis a la base de dades
            results_queue.put(result)  # Afegeix el resultat a la cua de result
        except Exception as e:
            conn.rollback()  # Si hi ha un error, desfem els canvis
            print(f"Error en executar la funció {func.__name__}: {e}")
            results_queue.put(e)
        finally:
            QUEUE.task_done()  # Marca la tasca com a completada
    
    cursor.close()
    conn.close()

def create_bandoler(cursor: sqlite3.Cursor, dicc_dades: dict) -> bool:
    try:
        cursor.execute("""
            INSERT INTO bandolers (id, nom, sobrenom, descripcio, estat, foto, kills, victima, punts, permis_instagram)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dicc_dades['id'], dicc_dades['nom'], dicc_dades['sobrenom'], dicc_dades['descripcio'], dicc_dades['estat'], dicc_dades['foto'], dicc_dades['kills'], dicc_dades['victima'], dicc_dades['punts'], dicc_dades['permis_instagram']))
        return True
    except (KeyError, sqlite3.Error) as e:
        print(f"Error ####{e}#### al crear un bandoler amb dades: \n{dicc_dades}")
        return False

def update(cursor: sqlite3.Cursor, field: str, id: int, value) -> None:
    cursor.execute(f"UPDATE bandolers SET {field}=? WHERE id=?", (value, id))

def set_winner(cursor: sqlite3.Cursor, id: int) -> None:
    cursor.execute("UPDATE variables SET valor=? WHERE nom='guanyador'", (str(id),))

def delete_user_from_db(cursor: sqlite3.Cursor, id: int) -> None:
    cursor.execute("DELETE FROM bandolers WHERE id=?", (id,))
    cursor.connection.commit()

######  altres funcions ######

def get_inscripcio_disponible(cursor: sqlite3.Cursor) -> bool:
    cursor.execute("SELECT valor FROM variables WHERE nom='inscripcio_disponible'")
    valor = cursor.fetchone()
    return True if valor[0] == 'True' else False

def file_content_2_string(file_name):
    # If a relative path is provided (e.g. './comandes/inicials.txt'), resolve it
    # relative to the project root (parent directory of this file).
    path = file_name
    if not os.path.isabs(path):
        path = os.path.join(get_dir_pare(), path)

    try:
        with open(path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        # Fallback: try opening the original file_name as-is (process CWD)
        try:
            with open(file_name, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Error obrint fitxer {file_name}: {e}")
            return ''

def id_in_db(cursor: sqlite3.Cursor, id: int) -> bool:
    cursor.execute("SELECT id FROM bandolers WHERE id=?", (id,))
    if cursor.fetchone() is None:
        return False
    else:
        return True

def get_user(cursor: sqlite3.Cursor, id: int) -> list:
    cursor.execute("SELECT * FROM bandolers WHERE id=?", (id,))
    user = cursor.fetchone()
    return list(user)

def get_all_bandolers(cursor: sqlite3.Cursor) -> list:
    cursor.execute("SELECT id FROM bandolers WHERE estat='jugant'")
    bandolers = cursor.fetchall()
    return [p[0] for p in bandolers]  # Retorna una llista d'ids dels bandolers jugant

def get_all_enxampats(cursor: sqlite3.Cursor) -> list:
    cursor.execute("SELECT id FROM bandolers WHERE estat='mort'")
    enxampats = cursor.fetchall()
    return [e[0] for e in enxampats]  # Retorna una llista d'ids dels enxampats

def get_all_pending(cursor: sqlite3.Cursor) -> list:
    cursor.execute("SELECT id FROM bandolers WHERE estat='pendent'")
    pendents = cursor.fetchall()
    return [p[0] for p in pendents]  # Retorna una llista d'ids dels pendents

def get_all_users(cursor: sqlite3.Cursor) -> list:
    cursor.execute("SELECT id FROM bandolers")
    users = cursor.fetchall()
    return [u[0] for u in users]  # Retorna una llista d'ids dels usuaris

def get_playing_users(cursor: sqlite3.Cursor) -> list:
    cursor.execute("SELECT id FROM bandolers WHERE estat!='mort'")
    playing_users = cursor.fetchall()
    return [u[0] for u in playing_users]  # Retorna una llista d'ids dels usuaris jugant

def blob_to_image(blob: bytes, bot, id_reciever, msg) -> str:
    img_stream = io.BytesIO(blob)
    img_stream.seek(0)  # Assegura que comencem a llegir des del principi

    bot.send_photo(id_reciever, img_stream, caption=msg)

def is_admin(message) -> bool:
    if message.from_user.id == ADMIN_ID:
        return True
    else:
        return False

# def ranquing_nuclis(cursor: sqlite3.Cursor):
#     cursor.execute("SELECT nucli, COUNT(*) as participants FROM bandolers GROUP BY nucli ORDER BY participants DESC")
#     ranquing = cursor.fetchall()
#     return list(ranquing)

def ranquing_bandolers(cursor: sqlite3.Cursor) -> list:
    cursor.execute("SELECT nom, sobrenom, punts, kills FROM bandolers WHERE punts>0 ORDER BY punts DESC, kills DESC LIMIT 10")
    ranquing = cursor.fetchall()
    return list(ranquing)

def graveyard(cursor: sqlite3.Cursor):
    id_winner = get_winner_from_var(cursor)
    cursor.execute("SELECT id FROM bandolers WHERE estat='mort'")
    morts = [u[0] for u in list(cursor.fetchall())]
    return morts if id_winner is None else [m for m in morts if m != id_winner]

def assign_victims_cyclic(cursor: sqlite3.Cursor) -> None:
    cursor.execute("SELECT id FROM bandolers WHERE estat != 'mort'")
    llista_bandolers = list(cursor.fetchall())

    random.shuffle(llista_bandolers)  # Barregem els bandolers per assignar víctimes aleatòriament

    num_bandolers = len(llista_bandolers)
    if num_bandolers < 2:
        print("No hi ha prou bandolers per assignar víctimes.")
    else:
        # Assignar víctimes de manera cíclica
        for i in range(num_bandolers):
            bandoler_id = llista_bandolers[i][0]
            # Assignar la víctima al bandoler actual
            update(cursor, 'victima', bandoler_id, llista_bandolers[(i + 1) % num_bandolers][0])
    return

def get_user_id_by_name(cursor: sqlite3.Cursor, name: str) -> int:
    cursor.execute("SELECT id FROM bandolers WHERE nom=?", (name,))
    user_id = cursor.fetchone()

    return user_id[0] if user_id else None  

    
def get_cycle(cursor: sqlite3.Cursor) -> list[int]:
    cursor.execute("SELECT COUNT(*) FROM bandolers WHERE estat='jugant'")
    n = cursor.fetchone()[0]
    cursor.execute("SELECT * FROM bandolers WHERE estat='jugant' LIMIT 1")
    first_bandoler = cursor.fetchone()

    ids = [first_bandoler[0]] 
    victima = first_bandoler[8]  # La víctima del primer bandoler
    for i in range(n):
        cursor.execute("SELECT victima FROM bandolers WHERE estat='jugant' AND id=?", (victima,))
        victima = cursor.fetchone()
        ids.append(victima[0])

    return ids[:-1] # Excloem l'últim perquè és el primer, per completar el cicle

def text_cycle(cursor: sqlite3.Cursor) -> str:
    ids = get_cycle(cursor)
    if not ids:
        return "No hi ha bandolers vius per mostrar el cicle."
    text = "Cicle de bandolers vius:\n"
    for i, id in enumerate(ids):
        user = name_or_surname(cursor, id)
        next_user = name_or_surname(cursor, ids[(i + 1) % len(ids)])
        if user:
            text += f"{i+1}. {user} --> {next_user}\n"
    return text.strip()

def get_killer(cursor: sqlite3.Cursor, id: int) -> int: # retorna l'id del bandoler que ha de matar a l'usuari amb id id
    cursor.execute(f"SELECT * FROM bandolers WHERE victima={id}")
    bandoler = cursor.fetchone()
    return bandoler[0] if bandoler else None  # Retorna l'id del bandoler que ha de matar

def kill(cursor: sqlite3.Cursor, id_mort: int) -> None:
    id_bandoler = get_killer(cursor, id_mort)  # Obtenim el bandoler que ha de matar
    if id_bandoler:
        new_victim = get_victim(cursor, id_mort)
        update(cursor, 'victima', id_bandoler, new_victim)
        update(cursor, 'estat', id_mort, 'mort')
        update(cursor, 'victima', id_mort, None)

def show_user(cursor: sqlite3.Cursor, id: int, bot, id_reciever) -> None:
    user = get_user(cursor, id)
    if user:
        msg = "ID: " + str(user[key2index('id')]) + "\n"
        msg += "Nom: " + user[key2index('nom')] + "\n"
        msg += "Sobrenom: " + user[key2index('sobrenom')] + "\n"
        msg += "Descripció: " + user[key2index('descripcio')] + "\n"
        msg += "Estat: " + user[key2index('estat')] + "\n"
        msg += "Kills: " + str(user[key2index('kills')]) + "\n"
        msg += "Victima: " + str(user[key2index('victima')]) + "\n"
        msg += "Punts: " + str(user[key2index('punts')]) + "\n"
        msg += "Permís Instagram: " + ("Sí" if user[key2index('permis_instagram')] else "No") + "\n"
        blob_to_image(user[key2index('foto')], bot, id_reciever, msg)
    else:
        msg = f"Usuari no trobat (ID: {id})."
        msg_admin = f"Usuari amb ID {id} no trobat per consulta de {id_reciever}. No es pot mostrar informació."
        bot.send_message(id_reciever, msg)
        bot.send_message(ADMIN_ID, msg_admin)  # Notificar l'administrador si l'usuari no es troba

def comprobar_dades_usuaris(cursor: sqlite3.Cursor, message, bot) -> bool:
    if is_admin(message):
        users = get_all_users(cursor)
        if not users:
            msg = "No hi ha usuaris registrats."
            bot.send_message(ADMIN_ID, msg)
            return False

        inscripcio_correcta = True
        for user in users:
            user = get_user(cursor, user)  # Obtenir dades de l'usuari
            if user[key2index('nom')] == '' or user[key2index('descripcio')] == '' or user[key2index('foto')] is None:
                inscripcio_correcta = False
                msg = f"Usuari {user[key2index('id')]} no està ben registrat. Falta informació."
                bot.send_message(ADMIN_ID, msg)
                msg_usuari = f"Hola estimat jugador! Sembla que la teva inscripció no està completa. Si us plau, torna a registrar-te si ho desitges enviant /inscripcio."
                delete_user_from_db(cursor, user[key2index('id')])  # Eliminar usuari de la base de dades
                bot.send_message(user[key2index('id')], msg_usuari)
        
        return inscripcio_correcta

def get_dir_pare() -> str:
    ruta_actual = os.path.abspath(__file__)
    dir_actual = os.path.dirname(ruta_actual)
    dir_pare = os.path.dirname(dir_actual)
    return dir_pare

def get_path_db() -> str:
    return os.path.join(get_dir_pare(), DB)

def get_path_comandes(type_command:str) -> str:
    ruta_actual = os.path.abspath(__file__)
    dir_actual = os.path.dirname(ruta_actual)
    path = os.path.join(dir_actual, 'comandes', type_command)
    return path

def get_path_messages(type_message:str) -> str:
    ruta_actual = os.path.abspath(__file__)
    dir_actual = os.path.dirname(ruta_actual)
    path = os.path.join(dir_actual, 'messages', type_message)
    return path

def get_not_playing_users(cursor: sqlite3.Cursor) -> list:
    cursor.execute("SELECT id FROM bandolers WHERE estat!='jugant'")
    not_playing_ids = cursor.fetchall()
    return [id[0] for id in not_playing_ids]

def get_players_with_kills(cursor: sqlite3.Cursor) -> list:
    cursor.execute("SELECT id FROM bandolers WHERE kills > 0")
    players_with_kills = cursor.fetchall()
    return [id[0] for id in players_with_kills]

def is_playing(cursor: sqlite3.Cursor, id: int) -> bool:
    cursor.execute("SELECT estat FROM bandolers WHERE id=?", (id,))
    estat = cursor.fetchone()
    return estat[0] == 'jugant' if estat else False

def is_dead(cursor: sqlite3.Cursor, id: int) -> bool:
    cursor.execute("SELECT estat FROM bandolers WHERE id=?", (id,))
    estat = cursor.fetchone()
    return estat[0] == 'mort' if estat else False

def is_pending(cursor: sqlite3.Cursor, id: int) -> bool:
    cursor.execute("SELECT estat FROM bandolers WHERE id=?", (id,))
    estat = cursor.fetchone()
    return estat[0] == 'pendent' if estat else False

def missatge_no_inscrits() -> str:
    inscripcio_disponible = execute_db(get_inscripcio_disponible)
    if inscripcio_disponible:
        msg = "No estàs registrat com a bandoler. \nPer registrar-te prem /inscripcio."
    else:
        msg = "No estàs registrat al joc."
    return msg

def get_state(cursor: sqlite3.Cursor, id: int) -> str:
    cursor.execute("SELECT estat FROM bandolers WHERE id=?", (id,))
    estat = cursor.fetchone()
    return estat[0] if estat else None

def get_names(cursor: sqlite3.Cursor, id:int) -> list[str]:
    cursor.execute("SELECT nom, sobrenom FROM bandolers WHERE id=?", (id,))
    names = cursor.fetchone()
    return list(names) if names else [None, None]  

def get_victim(cursor: sqlite3.Cursor, id: int) -> int:
    cursor.execute("SELECT victima FROM bandolers WHERE id=?", (id,))
    victim = cursor.fetchone()
    return victim[0] if victim else None  # Retorna l'id de la víctima o None si no hi ha cap víctima

def get_picture(cursor: sqlite3.Cursor, id: int) -> bytes:
    cursor.execute("SELECT foto FROM bandolers WHERE id=?", (id,))
    picture = cursor.fetchone()
    return picture[0] if picture else None  # Retorna la imatge o None si no hi ha cap imatge

# def get_nucli(cursor: sqlite3.Cursor, id: int) -> str:
#     cursor.execute("SELECT nucli FROM bandolers WHERE id=?", (id,))
#     nucli = cursor.fetchone()
#     return nucli[0] if nucli else None  # Retorna el nucli o None si no hi ha cap nucli

def get_kills(cursor: sqlite3.Cursor, id: int) -> int:
    cursor.execute("SELECT kills FROM bandolers WHERE id=?", (id,))
    kills = cursor.fetchone()
    return kills[0] if kills else 0  # Retorna el nombre de kills o 0 si no hi ha cap kill

def get_points(cursor: sqlite3.Cursor, id: int) -> int:
    cursor.execute("SELECT punts FROM bandolers WHERE id=?", (id,))
    points = cursor.fetchone()
    return points[0] if points else 0  # Retorna el nombre de punts o 0 si no hi ha cap punt

def get_name(cursor: sqlite3.Cursor, id: int) -> str:
    cursor.execute("SELECT nom FROM bandolers WHERE id=?", (id,))
    name = cursor.fetchone()
    return name[0] if name else None  # Retorna el nom o None si no hi ha cap nom

def name_or_surname(cursor: sqlite3.Cursor, id: int) -> str:
    cursor.execute("SELECT nom, sobrenom FROM bandolers WHERE id=?", (id,))
    names = cursor.fetchone()
    if names:
        return names[1] if names[1] != '' else names[0]
    return None  # Retorna None si no hi ha cap nom o sobrenom

def get_winner(cursor: sqlite3.Cursor) -> list[int]:
    cursor.execute(
        """
        WITH ranking AS (
            SELECT
                b.id,
                b.punts,
                b.kills,
                COUNT(cb.id_control) AS n_controls
            FROM bandolers b
            LEFT JOIN controls_bandolers cb ON cb.id_bandoler = b.id
            WHERE b.estat = 'jugant'
            GROUP BY b.id, b.punts, b.kills
        ), winner AS (
            SELECT id, punts, kills, n_controls
            FROM ranking
            ORDER BY punts DESC, kills DESC, n_controls DESC
            LIMIT 1
        )
        SELECT r.id
        FROM ranking r
        JOIN winner w
          ON r.punts = w.punts
         AND r.kills = w.kills
         AND r.n_controls = w.n_controls
        ORDER BY r.id
        """
    )
    winners = [row[0] for row in cursor.fetchall()]

    return winners if len(winners) > 0 else None

def n_bandolers(cursor: sqlite3.Cursor) -> int:
    cursor.execute("SELECT COUNT(*) FROM bandolers WHERE estat!='mort'")
    count = cursor.fetchone()
    return count[0] if count else 0

def get_winner_from_var(cursor: sqlite3.Cursor) -> int:
    # val 1 si s'ha acabat el joc i no hi ha gunayador
    cursor.execute("SELECT valor FROM variables WHERE nom='guanyador'")
    winner = cursor.fetchone()
    if winner and winner[0] != '0' and winner[0] != 'None':
        return int(winner[0])
    else:
        return None

def assert_no_bar(str: str) -> bool:
    # assegura que no hi hagi el caracter '/' a la cadena
    return '/' not in str

def date_in_range(date_str: str, inici: str, final: str) -> bool:
    # Comprova si la data donada està dins del rang especificat
    try:
        date_obj = date.fromisoformat(date_str)
        inici_obj = date.fromisoformat(inici)
        final_obj = date.fromisoformat(final)
        return inici_obj <= date_obj <= final_obj
    except ValueError:
        return False

def get_control_id_given_date(cursor: sqlite3.Cursor, date_str: str) -> int:
    cursor.execute("SELECT id FROM controls WHERE inici <= ? AND final >= ?", (date_str, date_str))
    control = cursor.fetchone()
    return control[0] if control else None

def is_user_in_control(cursor: sqlite3.Cursor, control_id: int, user_id: int) -> bool:
    cursor.execute("SELECT * FROM controls_bandolers WHERE id_control=? AND id_bandoler=?", (control_id, user_id))
    return cursor.fetchone() is not None

def add_user_to_control(cursor: sqlite3.Cursor, control_id: int, user_id: int, timestamp: str) -> None:
    cursor.execute("INSERT OR IGNORE INTO controls_bandolers (id_control, id_bandoler, timestamp) VALUES (?, ?, ?)", (control_id, user_id, timestamp))

def control_points(cursor: sqlite3.Cursor, id_bandoler: int, timestamp: str) -> int:
    # Aquesta funció assigna punts segons l'hora del control
    # si és el primer control del dia, assigna 1 punt
    # si no, assigna 2 punts
    control_id = get_control_id_given_date(cursor, timestamp)
    cursor.execute("SELECT dia FROM controls WHERE id=?", (control_id,))
    control_day = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM controls_bandolers WHERE id_bandoler=? AND id_control IN (SELECT id FROM controls WHERE dia=?)", (id_bandoler, control_day))
    count = cursor.fetchone()[0]

    print(f"Bandoler {id_bandoler} ha realitzat {count} controls el dia {control_day}.")
    return 1 if count == 1 else 2

def index2key(index: int) -> str:
    return BANDOLER_FIELD_NAMES[index] if index in BANDOLER_FIELD_NAMES else None

def key2index(key: str) -> int:
    for index, field_name in BANDOLER_FIELD_NAMES.items():
        if field_name == key:
            return index
    return None 

def get_all_controls(cursor: sqlite3.Cursor) -> list:
    cursor.execute("SELECT * FROM controls")
    controls = cursor.fetchall()
    return [list(control) for control in controls]  # Retorna una llista de llistes amb tots els controls

def get_next_control(cursor: sqlite3.Cursor, current_timestamp: str) -> dict:
    cursor.execute("SELECT * FROM controls WHERE inici > ? ORDER BY inici ASC LIMIT 1", (current_timestamp,))
    next_control = cursor.fetchone()
    if next_control:
        control_dict = {
            'id': next_control[0],
            'inici': next_control[1],
            'final': next_control[2],
            'dia': next_control[3]
        }
    return control_dict if next_control else None  # Retorna el proper control o None si no hi ha cap

def data_strip(data: str) -> tuple:
    # Retorna dia, mes, any, hora i minuts per separat
    date_part, time_part = data.split(' ')
    year, month, day = date_part.split('-')
    hour, minute, second = time_part.split(':')
    return day, month, year, hour, minute, second

def format_data(day: str, month: str, year: str, hour: str, minute: str, second: str) -> str:
    # Retorna la data en format 'YYYY-MM-DD HH:MM:SS'
    return f"{year}-{month}-{day} {hour}:{minute}:{second}"


def next_control_message(inici: str, final: str) -> str:
    inici_day, inici_month, inici_year, inici_hour, inici_minute, _ = data_strip(inici)
    final_day, final_month, final_year, final_hour, final_minute, _ = data_strip(final)
    
    if inici_day == final_day and inici_month == final_month and inici_year == final_year:
        return f"El proper control serà el dia {inici_day}/{inici_month}/{inici_year} de {inici_hour}:{inici_minute} fins a les {final_hour}:{final_minute}."
    else:
        return f"El proper control serà del dia {inici_day}/{inici_month}/{inici_year} a les {inici_hour}:{inici_minute} fins al dia {final_day}/{final_month}/{final_year} a les {final_hour}:{final_minute}."

def get_completed_controls(cursor: sqlite3.Cursor) -> list:
    # Retorna una llista de tuples amb els controls completats, ordenats per persona i data (0: id_bandoler, 1: id_control, 2: timestamp)
    cursor.execute("""
        SELECT cb.id_bandoler, cb.id_control, cb.timestamp
        FROM controls_bandolers cb
        ORDER BY cb.id_bandoler, cb.timestamp
    """)
    completed_controls = cursor.fetchall()
    _list = [list(control) for control in completed_controls]
    return _list

def get_user_controls(cursor: sqlite3.Cursor, user_id: int) -> list:
    cursor.execute("""
        SELECT cb.id_control, cb.id_bandoler, cb.timestamp
        FROM controls_bandolers as cb
        WHERE cb.id_bandoler = ?
    """, (user_id,))
    user_controls = cursor.fetchall()
    return [list(control) for control in user_controls]

def obrir_inscripcions(cursor: sqlite3.Cursor, bot) -> None:
    valor = execute_db(get_inscripcio_disponible)
    if not valor:
        execute_db(change_inscripcio_disponible)
        msg = "Les inscripcions s'han obert. Ara els usuaris poden registrar-se.\n"
    else:
        msg = "Les inscripcions ja estan obertes.\n"
    bot.send_message(ADMIN_ID, msg)

def update_state_and_kills_2_start(cursor: sqlite3.Cursor) -> None:
   for user in get_all_users(cursor):
       update(cursor, 'estat', user, 'jugant')
       update(cursor, 'kills', user, 0)

def comencar_joc(cursor: sqlite3.Cursor, bot) -> None:
    execute_db(update_state_and_kills_2_start)
    execute_db(set_winner, 0)  # Resetejar guanyador
    # Tancar inscripcions
    if execute_db(get_inscripcio_disponible):
        execute_db(change_inscripcio_disponible)
    # Assignar víctimes
    assign_victims_cyclic(cursor)
    msg_admin = "S'han posat a tots els usuaris com a jugant amb 0 kills i s'han assignat les víctimes.\n/usuaris per veure els usuaris registrats.\n\n"
    msg_admin += "El joc ha començat!"
    bot.send_message(ADMIN_ID, msg_admin)
    send_message_to_target('Tots els usuaris', file_content_2_string(get_path_messages("start.txt")), bot)

def send_message_to_target(target:str, text: str, bot) -> None:
    match target:
        case 'Bandolers':
            users = execute_db(get_all_bandolers)
        case 'Enxampats':
            users = execute_db(get_all_enxampats)
        case 'Pendents':
            users = execute_db(get_all_pending)
        case 'Tots els usuaris':
            users = execute_db(get_all_users)
        case 'Cancel·lar':
            msg = "Enviament de missatge cancel·lat."
            bot.send_message(ADMIN_ID, msg)
            return
        case _:
            users = [execute_db(get_user_id_by_name, target)]

    for user_id in users:
        print(f"enviant missatge a usuari {f.execute_db(get_name, user_id)} amb ID {user_id}")
        bot.send_message(user_id, text)
        time.sleep(0.05)  # Petita pausa per evitar problemes amb l'enviament massiu

    msg = f"Missatge enviat a {target}."
    bot.send_message(ADMIN_ID, msg)

@telegram_safe
def send_winning_message(bot, id_winners: list[int]) -> None:
    """
    Envia missatge de guanyador a tots els participants
    """
    execute_db(set_winner, id_winners[0])
    for id_winner in id_winners:
        execute_db(update, 'estat', id_winner, 'mort') # TODO: en un futur fer estat guanyador
        execute_db(update, 'victima', id_winner, None)
    
    name_winners = [execute_db(name_or_surname, id_winner) for id_winner in id_winners]
    kills = execute_db(get_kills, id_winners[0])
    punts = execute_db(get_points, id_winners[0])
    n_controls = len(execute_db(get_user_controls, id_winners[0]))
    if len(id_winners) == 1:
        msg_bandoler = "\n\nFELICITATS! Ets bandoler el bandoler guanyador!"
        msg_bandoler += f"\nHas aconseguit {punts} punts fent {kills} kills"
        msg_bandoler += "\nEl @SheriffDeDosrius es posarà amb contacte amb tu per coordinar la teva recompensa!"
        msg_bandoler += "\n\nGràcies per participar!"

        msg_participants = f"\n\nATENCIÓ: Tenim bandoler guanyador, felicitats {name_winners[0]}🤠!!!"
        msg_participants += f"\nQue ha aconseguit {punts} punts fent {kills} kills"
        msg_participants += "\nGràcies a tots per participar, esperem que us hagi agradat!"

    elif len(id_winners) > 1:
        msg_bandoler = "\n\nFELICITATS! Ets un dels bandolers guanyadors, has quedat empatat amb altres bandolers!"
        msg_bandoler += "\nEl @SheriffDeDosrius es posarà amb contacte amb tu i els altres per coordinar la vostra recompensa!"
        msg_bandoler += "\n\nGràcies per participar!"

        msg_participants = f"\n\nATENCIÓ: Tenim els bandolers guanyadors, felicitats {', '.join(name_winners[:-1])} i {name_winners[-1]}!!!"
        msg_participants += f"\nHan quedat empat fent {punts} punts amb {kills} kills"
        msg_participants += "\nGràcies a tots per participar, esperem que us hagi agradat!"

    # Enviar la foto de l'últim bandoler + missatge a tots els participants
    picture_winners = [execute_db(get_picture, id_winner) for id_winner in id_winners]
    for user_id in execute_db(get_all_users)+[ADMIN_ID]:
        for picture_winner in picture_winners:
            blob_to_image(picture_winner, bot, user_id, '')
        bot.send_message(user_id, msg_participants)
        msg = "Si teniu algun comentari o suggeriment sobre el joc, no dubteu a enviar un missatge al @SheriffDeDosrius. \nEns encantaria escoltar la vostra opinió!"
        bot.send_message(user_id, msg)

    for id_winner in id_winners:
        bot.send_message(id_winner, msg_bandoler)

def kill_runaway(bot, id_user, dia) -> None:
    print(f"Executant kill_runaway per l'usuari amb ID {id_user}")
    name_user = execute_db(name_or_surname, id_user)
    print(f"nom: {name_user}")

    motive = f"{name_user} ha estat declarat fugitiu per no presentar-se a cap Control de Bandolers del dia. El Sheriff l'ha declarat mort! ACS🔫🕊"

    killer = execute_db(get_killer, id_user)
    print(f"killer: {killer}")
    execute_db(kill, id_user)
    print(f"funció kill executada per l'usuari amb ID {id_user}.")

    send_message_to_target('Tots els usuaris', motive, bot)
    bot.send_message(ADMIN_ID, motive)

    num_bandolers = execute_db(n_bandolers)
    print(f"n_bandolers: {num_bandolers}")
    msg_participants = f"Queden {num_bandolers} bandolers en joc🏜"
    send_message_to_target('Tots els usuaris', msg_participants, bot)
    bot.send_message(ADMIN_ID, msg_participants)

    victima = execute_db(get_victim, killer)
    print(f"victima: {victima}")
    if victima is None:
        send_message_to_target('Tots els usuaris', file_content_2_string(get_path_messages("case_everyone_loses.txt")), bot)
        return
    # print(f"user: {id_user}, killer: {killer}, victima de killer: {victima}")
    if victima == killer:
        if killer in execute_db(get_users_with_no_day_controls, dia):
            execute_db(set_winner, 1)  # Resetejar guanyador
            return
        send_winning_message(bot, [killer]) 
    else:
        msg_killer = f"La teva víctima ha estat actualitzada. Pots veure la seva informació prement /victima."
        bot.send_message(killer, msg_killer)

def get_users_with_no_day_controls(cursor: sqlite3.Cursor, dia: int) -> list[int]:
    """
    Retorna una llista amb els IDs d'usuari de tots els usuaris que no tenen controls assignats per al dia especificat
    """
    query = """
    SELECT id FROM bandolers
    EXCEPT
    SELECT DISTINCT id_bandoler FROM controls_bandolers WHERE id_control IN (
        SELECT id FROM controls WHERE dia = ?
    )
    """
    cursor.execute(query, (dia,))
    result = cursor.fetchall()
    return [row[0] for row in result] if result else []

def get_users_with_no_control(cursor: sqlite3.Cursor, control_id: str) -> list[int]:
    """
    Retorna una llista amb els IDs d'usuari de tots els usuaris que no han fet el control especificat
    """
    cursor.execute("SELECT id FROM bandolers EXCEPT SELECT id_bandoler FROM controls_bandolers WHERE id_control = ?", (control_id,))
    result = cursor.fetchall()
    return [row[0] for row in result] if result else []

def get_day_last_control_date(cursor: sqlite3.Cursor) -> int:
    # retorna el dia de l'ultim control programat
    cursor.execute("SELECT inici FROM controls ORDER BY inici DESC LIMIT 1")
    result = cursor.fetchone()
    return result[0] if result else None

def get_day_last_control(cursor: sqlite3.Cursor) -> int:
    _date = get_day_last_control_date(cursor)
    if _date:
        day, _, _, _, _, _ = data_strip(_date)
        return int(day)
    else:
        return None
