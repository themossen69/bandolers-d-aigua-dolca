import sqlite3
import io
import random
import os
import queue
import sys

private_path = os.path.abspath(os.path.join(os.getcwd(), "..", "_private", "constants"))
if private_path not in sys.path:
    sys.path.insert(0, private_path)

from constants import ADMIN_ID, DB, QUEUE

###### funcions de gestió de la base de dades ######

def create_DB(cursor) -> None:
    # Crear la taula "bandolers" amb relació recursiva
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bandolers (
        id INTEGER PRIMARY KEY,
        nom TEXT NOT NULL,
        sobrenom TEXT,
        nucli TEXT CHECK (nucli IN ('Dosrius', 'Canyamars', 'Can Massuet', '')),
        descripcio TEXT,
        estat TEXT CHECK (estat IN ('jugant', 'mort', 'pendent')),
        foto BLOB,
        kills INTEGER DEFAULT 0,
        victima INTEGER,
        punts INTEGER DEFAULT 0,
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

def restart_db(cursor: sqlite3.Cursor) -> None:
    cursor.execute("DROP TABLE IF EXISTS bandolers")
    cursor.connection.commit()
    create_DB(cursor)  # Re-crea la base de dades després de reiniciar
    print("Base de dades reiniciada.")

def change_inscripcio_disponible(cursor: sqlite3.Cursor) -> None:
    valor = get_inscripcio_disponible(cursor)
    cursor.execute("UPDATE variables SET valor=? WHERE nom='inscripcio_disponible'", (str(not valor),))

def execute_db(func, *args: tuple, timeout=5):
    results_queue = queue.Queue() # Crea una cua per emmagatzemar els resultats
    QUEUE.put((func, args, results_queue))  # Afegeix la funció i els arguments a la cua
    try:
        return results_queue.get(timeout=timeout)  # Espera i retorna el resultat de la funció
    except queue.Empty:
        print("Operació de BD caducada")

def db_worker():
    conn = sqlite3.connect(get_path_db(), check_same_thread=False, timeout=10) # TODO: troban nº adequat
    cursor = conn.cursor()

    create_DB(cursor)  # Assegura que la base de dades està creada abans de començar a processar esdeveniments
    conn.commit()

    while True:
        func, args, results_queue = QUEUE.get()
        if func is None:  # Si la funció és None, sortim del bucle
            break
        try:
            result = func(cursor, *args)  # Executa la funció amb el cursor i els arguments
            conn.commit()  # Commit els canvis a la base de dades
            results_queue.put(result)  # Afegeix el resultat a la cua de result
        except Exception as e:
            conn.rollback()  # Si hi ha un error, desfem els canvis
            print(f"Error en executar la funció {func.__name__}: {e}")
            results_queue.put(e)
    
    cursor.close()
    conn.close()

def create_bandoler(cursor: sqlite3.Cursor, dicc_dades: dict) -> bool:
    try:
        cursor.execute("""
            INSERT INTO bandolers (id, nom, nucli, descripcio, estat, sobrenom, victima, foto, kills, punts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dicc_dades['id'], dicc_dades['nom'], dicc_dades['nucli'], dicc_dades['descripcio'], dicc_dades['estat'], dicc_dades['sobrenom'], dicc_dades['victima'], dicc_dades['foto'], dicc_dades['kills'], dicc_dades['punts']))
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

def blob_to_image(blob: bytes, bot, id_reciever, msg) -> str:
    img_stream = io.BytesIO(blob)
    img_stream.seek(0)  # Assegura que comencem a llegir des del principi

    bot.send_photo(id_reciever, img_stream, caption=msg)

def is_admin(message) -> bool:
    if message.from_user.id == ADMIN_ID:
        return True
    else:
        return False

def ranquing_nuclis(cursor: sqlite3.Cursor):
    cursor.execute("SELECT nucli, COUNT(*) as participants FROM bandolers GROUP BY nucli ORDER BY participants DESC")
    ranquing = cursor.fetchall()
    return list(ranquing)

def ranquing_bandolers(cursor: sqlite3.Cursor):
    cursor.execute("SELECT nom, sobrenom, kills FROM bandolers WHERE kills>0 ORDER BY kills DESC LIMIT 10")
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

def killer(cursor: sqlite3.Cursor, id: int) -> int: # retorna l'id del bandoler que ha de matar a l'usuari amb id id
    cursor.execute(f"SELECT * FROM bandolers WHERE victima={id}")
    bandoler = cursor.fetchone()
    return bandoler[0] if bandoler else None  # Retorna l'id del bandoler que ha de matar

def kill(cursor: sqlite3.Cursor, id_mort: int) -> None:
    id_bandoler = killer(cursor, id_mort)  # Obtenim el bandoler que ha de matar
    if id_bandoler:
        new_victim = get_victim(cursor, id_mort)
        update(cursor, 'victima', id_bandoler, new_victim)
        update(cursor, 'estat', id_mort, 'mort')
        update(cursor, 'victima', id_mort, None)

def show_user(cursor: sqlite3.Cursor, id: int, bot, id_reciever) -> None:
    user = get_user(cursor, id)
    if user:
        msg = "ID: " + str(user[0]) + "\n"
        msg += "Nom: " + user[1] + "\n"
        msg += "Sobrenom: " + user[2] + "\n"
        msg += "Nucli: " + user[3] + "\n"
        msg += "Descripció: " + user[4] + "\n"
        msg += "Estat: " + user[5] + "\n"
        msg += "Kills: " + str(user[7]) + "\n"
        msg += "Victima: " + str(user[8]) + "\n"
        blob_to_image(user[6], bot, id_reciever, msg)
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
            if user[1] == '' or user[3] == '' or user[4] == '' or user[6] is None:
                inscripcio_correcta = False
                msg = f"Usuari {user[0]} no està ben registrat. Falta informació."
                bot.send_message(ADMIN_ID, msg)
                msg_usuari = f"Hola estimat jugador! Sembla que la teva inscripció no està completa. Si us plau, torna a registrar-te si ho desitges enviant /inscripcio."
                delete_user_from_db(cursor, user[0])  # Eliminar usuari de la base de dades
                bot.send_message(user[0], msg_usuari)
        
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
    global inscripcio_disponible
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

def get_nucli(cursor: sqlite3.Cursor, id: int) -> str:
    cursor.execute("SELECT nucli FROM bandolers WHERE id=?", (id,))
    nucli = cursor.fetchone()
    return nucli[0] if nucli else None  # Retorna el nucli o None si no hi ha cap nucli

def get_kills(cursor: sqlite3.Cursor, id: int) -> int:
    cursor.execute("SELECT kills FROM bandolers WHERE id=?", (id,))
    kills = cursor.fetchone()
    return kills[0] if kills else 0  # Retorna el nombre de kills o 0 si no hi ha cap kill

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

def get_winner(cursor: sqlite3.Cursor) -> int:
    cursor.execute("SELECT id FROM bandolers WHERE estat='jugant' and id = victima")
    winner = cursor.fetchone()
    return winner[0] if winner else None

def n_bandolers(cursor: sqlite3.Cursor) -> int:
    cursor.execute("SELECT COUNT(*) FROM bandolers WHERE estat!='mort'")
    count = cursor.fetchone()
    return count[0] if count else 0

def get_winner_from_var(cursor: sqlite3.Cursor) -> int:
    cursor.execute("SELECT valor FROM variables WHERE nom='guanyador'")
    winner = cursor.fetchone()
    return int(winner[0]) if winner and winner[0] != '0' else None

def assert_no_bar(str: str) -> bool:
    # assegura que no hi hagi el caracter '/' a la cadena
    return '/' not in str



if __name__ == "__main__":
    # print(file_content_2_string(get_path_comandes('inicials.txt')))
    # print(f"cadena: {'holano'} -> {assert_no_bar('holano')}")
    pass