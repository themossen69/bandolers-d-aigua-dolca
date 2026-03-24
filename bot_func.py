import telebot
import os
import sqlite3
import sys

from telebot.types import ReplyKeyboardRemove
from telebot.types import ReplyKeyboardMarkup

import functions as f

private_path = os.path.abspath(os.path.join(os.getcwd(), "..", "_private", "constants"))
if private_path not in sys.path:
    sys.path.insert(0, private_path)
from constants import TOKEN, ADMIN_ID

bot: telebot.TeleBot = telebot.TeleBot(TOKEN)

# COMANDS
@bot.message_handler(commands=['start'])
def start(message) -> None:
    msg = f.file_content_2_string(f.get_path_messages("welcome.txt"))
    bot.send_message(message.chat.id, msg, reply_markup=ReplyKeyboardRemove())

@bot.message_handler(commands=['comandes_disponibles'])
def ajuda(message) -> None:
    # print("Comandes disponibles: ", message)
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        if f.execute_db(f.id_in_db, user_id):
            user_state = f.execute_db(f.get_state, user_id)
            if f.execute_db(f.get_inscripcio_disponible):
                msg = f.file_content_2_string(f.get_path_comandes('inicials.txt'))
            else:
                if user_state == 'jugant':
                    msg = f.file_content_2_string(f.get_path_comandes('bandolers.txt'))
                elif user_state == 'mort':
                    msg = f.file_content_2_string(f.get_path_comandes('enxampats.txt'))
                else:
                    msg = f.file_content_2_string(f.get_path_comandes('pendents.txt'))
            bot.send_message(user_id, msg, reply_markup=ReplyKeyboardRemove())
        else:
            bot.send_message(user_id, f.missatge_no_inscrits(), reply_markup=ReplyKeyboardRemove())

    else:
        msg = f.file_content_2_string(f.get_path_comandes('admin.txt'))

        bot.send_message(message.chat.id, msg, reply_markup=ReplyKeyboardRemove())

@bot.message_handler(commands=['inscripcio'])
def registration(message) -> None:
    # si no existeix la bd crear-la
    if not f.execute_db(f.get_inscripcio_disponible):
        msg = "Les inscripcions estan tancades."
        bot.send_message(message.chat.id, msg)
    else: 
        if not os.path.exists(f.get_path_db()):
            f.execute_db(f.create_DB)

        if f.execute_db(f.id_in_db, message.from_user.id): 
            msg = "Usuari ja registrat"
            bot.send_message(message.chat.id, msg)
        else:
            if message.from_user.id != ADMIN_ID:
                print("Begin inscripcio combined")
                dicc_user = dict()
                dicc_user['id'] = message.from_user.id
                dicc_user['kills'] = 0 
                dicc_user['estat'] = 'jugant'
                dicc_user['victima'] = 0
                dicc_user['sobrenom'] = ''
                dicc_user['punts'] = 0

                msg = "Introdueix per teclat nom i cognoms:\n"
                bot.send_message(message.chat.id, msg)
                bot.register_next_step_handler(message, lambda m: check_name(dicc_user, m))
                print("End inscripcio combined")
            else:
                msg = "No et pots registrar com a bandoler, ets l'administrador del bot."
                bot.send_message(message.chat.id, msg)

def check_name(dicc_user: dict, message) -> None:
    name = message.text
    if not f.assert_no_bar(name):
        msg = "El nom no pot contenir el caràcter '/'. Torna a intentar-ho."
        bot.send_message(message.chat.id, msg)
        bot.register_next_step_handler(message, lambda m: check_name(dicc_user, m))
        return
    dicc_user['nom'] = name

    markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
    markup.add('Dosrius', 'Canyamars', 'Can Massuet')
    message = bot.send_message(message.chat.id, "De quin nucli de Dosrius ets? (Prem un dels 3 botons)", reply_markup=markup)
    bot.register_next_step_handler(message, lambda m: add_nucli(dicc_user, m))


def add_nucli(dicc_user: dict, message) -> None:
    nucli = message.text
    if nucli in ['Dosrius', 'Canyamars', 'Can Massuet']:
        dicc_user['nucli'] = nucli
        msg = "Introdueix una descripció de tu mateix que inclogui els teus trets físics més característics (perquè els altres bandolers et puguin reconèixer).\n"
        #msg += "Per exemple: 'Sóc un bandoler molt perillós que roba a la gent de Canyamars'.\n"
        bot.send_message(message.chat.id, msg)
        bot.register_next_step_handler(message, lambda m: check_description(dicc_user, m))
    else:
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
        markup.add('Dosrius', 'Canyamars', 'Can Massuet')
        msg = "No s'ha pogut registrar el nucli. Torna a intentar-ho. \n\nIMPORTANT: Prem un dels 3 botons (Si no escriu: Dosrius, Canyamars o Can Massuet)."
        bot.send_message(message.chat.id, msg, reply_markup=markup)
        bot.register_next_step_handler(message, lambda m: add_nucli(dicc_user, m))

def check_description(dicc_user: dict, message) -> None:
    description = message.text
    if not f.assert_no_bar(description):
        msg = "La descripció no pot contenir el caràcter '/'. Torna a intentar-ho."
        bot.send_message(message.chat.id, msg)
        bot.register_next_step_handler(message, lambda m: check_description(dicc_user, m))
        return
    dicc_user['descripcio'] = description
    msg = "Introdueix una foto teva (envia una imatge que se't vegi bé la cara).\n"
    bot.send_message(message.chat.id, msg)
    bot.register_next_step_handler(message, lambda m: save_photo(dicc_user, m))

def save_photo(dicc_user: dict, message) -> None:
    if message.content_type == 'photo':  # Comprova si el missatge conté una foto
        # Obtenir la millor resolució de la foto
        file_id = message.photo[-1].file_id  # L'últim element té la millor qualitat
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path

        # Descarregar la imatge amb telebot
        file_data = bot.download_file(file_path)

        # Guardar la imatge com un blob a la base de dades
        dicc_user['foto'] = sqlite3.Binary(file_data)

        inscripcio_correcta = f.execute_db(f.create_bandoler, dicc_user)

        if not inscripcio_correcta:
            msg = "No s'ha pogut registrar la inscripció, falten dades. Torna-ho a intentar amb /inscripcio."
            bot.send_message(message.chat.id, msg)
            return

        msg = "Inscripció registrada correctament!\n\n"
        msg += "Per veure el teu perfil prem /perfil.\n"
        msg += "Per veure les comandes disponibles prem /comandes_disponibles.\n"
        # msg += "Si vols pots posar-te un sobrenom. Prem /actualitzar_sobrenom per canviar-lo.\n"
        bot.send_message(message.chat.id, msg)
    else:
        msg = "No has enviat una imatge amb un format correcte. Torna a intentar-ho. \n\nSi veus que no funciona, fes-te una foto des de la càmera de telegram i envia-la."
        bot.send_message(message.chat.id, msg)
        bot.register_next_step_handler(message, lambda m: save_photo(dicc_user, m))

def user_and_victim(cursor: sqlite3.Cursor, id_bandoler: int) -> tuple:
    """
    Retorna una tupla amb l'usuari i la seva víctima.
    """
    try:
        user = f.get_user(cursor, id_bandoler)
        victim_id = user[8]  # Victima assignada
        victim = f.get_user(cursor, victim_id)
        return user, victim
    except Exception as e:
        print(f"Error en obtenir l'usuari o la víctima: {e}")
        return None, None

@bot.message_handler(commands=['victima'])
def show_victim_profile(message):
    if f.execute_db(f.id_in_db, message.from_user.id):
        user, bandoler = f.execute_db(user_and_victim, message.from_user.id)
        if user is None or bandoler is None:
            bot.send_message(message.chat.id, "No s'ha pogut obtenir la informació de l'usuari o la víctima.")
            return
        if user[5] == 'jugant':
            # bandoler = f.get_user(user[8])
            if bandoler:
                if bandoler[2] != '':
                    msg = f"{bandoler[1]} aka {bandoler[2]}\n\n"
                else:
                    msg = f"{bandoler[1]}\n\n"

                msg += bandoler[4] # description

                f.blob_to_image(bandoler[6], bot, message.chat.id, msg)
            else:
                msg = "No tens víctima assignada.\n Contacta amb @SheriffDeDosrius per solucionar-ho."
                bot.send_message(message.chat.id, msg)
        elif user[5] == 'pendent':
            msg = "No pots veure el perfil de la teva víctima perquè estàs pendent de confirmar un enxampament.\n"
            msg += "Prem /confirmar per confirmar l'enxampament o /denegar per denegar-lo."
            bot.send_message(message.chat.id, msg)
        else:  # mort
            msg = "No pots veure el perfil de la teva víctima perquè estàs eliminat...\n"
            msg += "Però no et preocupis, l'any que ve tornaràs a jugar!"
            bot.send_message(message.chat.id, msg)
    else:
        msg = f.missatge_no_inscrits()
        bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['perfil'])
def show_profile(message):
    if not f.execute_db(f.id_in_db, message.from_user.id):
        bot.send_message(message.chat.id, f.missatge_no_inscrits())
        return
    user = f.execute_db(f.get_user, message.from_user.id)
    msg = "Nom: " + user[1] + "\n"
    msg += "Sobrenom: " + user[2] + "\n"
    if user[2]=='':
        msg += "(Per posar-te sobrenom prem /editar_perfil i seguidament prem el botó corresponent.)\n"
    msg += "Descripció: " + user[4] + "\n"
    msg += "Nucli: " + user[3] + "\n"
    msg += "Estat: " + user[5] + "\n"
    msg += "Kills: " + str(user[7]) + "\n"

    f.blob_to_image(user[6], bot, message.chat.id, msg)


# @bot.message_handler(commands=['actualitzar_sobrenom'])
# def update_alias(message):
#     if f.execute_db(f.id_in_db, message.from_user.id):
#         msg = "Introdueix el sobrenom que vulguis posar-te:\n"
#         bot.send_message(message.chat.id, msg)
#         bot.register_next_step_handler(message, check_alias)
#     else:
#         bot.send_message(message.chat.id, f.missatge_no_inscrits())

# def check_alias(message):
#     alias = message.text
#     f.execute_db(f.update, 'sobrenom', message.from_user.id, alias)
#     msg = "Sobrenom actualitzat correctament!\n"
#     msg += "Per veure el teu perfil prem /perfil.\n"
#     msg += "Per veure les comandes disponibles prem /comandes_disponibles.\n"
#     bot.send_message(message.chat.id, msg)    

def id_state_names(cursor: sqlite3.Cursor, id_bandoler: int) -> tuple:
    """
    Retorna un tuple amb l'estat, el nom i el sobrenom del bandoler.
    """
    id_victima = f.get_victim(cursor, id_bandoler)
    state_bandoler = f.get_state(cursor, id_bandoler)
    state_victima = f.get_state(cursor, id_victima)
    name_bandoler = f.name_or_surname(cursor, id_bandoler)
    name_victima = f.name_or_surname(cursor, id_victima)

    return id_victima, state_bandoler, state_victima, name_bandoler, name_victima

@bot.message_handler(commands=['enxampar'])
def enxampar(message):
    if not f.execute_db(f.id_in_db, message.from_user.id):
        bot.send_message(message.chat.id, f.missatge_no_inscrits())
        return 
    state = f.execute_db(f.get_state, message.from_user.id)
    if state != 'jugant':
        msg = f"No pots enxampar ningú perquè estas en estat {state}."
        msg += "Prem /comandes_disponibles per veure les comandes que tens disponibles segons el teu estat."
        bot.send_message(message.chat.id, msg)
        return

    if f.execute_db(f.get_inscripcio_disponible):
        msg = "Les inscripcions estan obertes. No es pot enxampar ningú."
        bot.send_message(message.chat.id, msg)
        return

    id_bandoler = message.from_user.id
    id_victima, state_bandoler, state_victima, name_bandoler, name_victima = f.execute_db(id_state_names, id_bandoler)

    if state_bandoler == 'jugant' and state_victima == 'jugant':
        msg_bandoler = f"S'ha enviat un missatge a {name_victima} per confirmar que l'has enxampat."
        bot.send_message(id_bandoler, msg_bandoler)

        msg_victima = f"T'han enxampat?!\nPrem /confirmar per confirmar-ho o /denegar per denegar-ho."

        f.execute_db(f.update, 'estat', id_victima, 'pendent')  # Actualitzar l'estat de la víctima a pendent

        bot.send_message(id_victima, msg_victima)

    elif state_bandoler == 'jugant' and state_victima == 'pendent':
        msg = "La teva víctima està pendent de confirmació. Espera que confirmi o denegi l'enxampament."
        bot.send_message(message.chat.id, msg)

def updates_confirm(cursor: sqlite3.Cursor, id_bandoler: int, id_victima: int, victima_victima: int) -> str:
    kills = f.get_kills(cursor, id_bandoler)
    f.update(cursor, 'estat', id_victima, 'mort')
    f.update(cursor, 'victima', id_bandoler, victima_victima)
    f.update(cursor, 'victima', id_victima, 0)
    f.update(cursor, 'kills', id_bandoler, kills + 1)

@bot.message_handler(commands=['confirmar'])
def confirm_kill(message) -> None:
    if not f.execute_db(f.id_in_db, message.from_user.id):
        bot.send_message(message.chat.id, f.missatge_no_inscrits())
        return

    if not f.execute_db(f.is_pending, message.from_user.id):
        msg = "No tens cap enxampament pendent."
        bot.send_message(message.chat.id, msg)
    else:
        id_victima = message.from_user.id
        id_bandoler = f.execute_db(f.killer, id_victima)

        victima_victima = f.execute_db(f.get_victim, id_victima)

        f.execute_db(updates_confirm, id_bandoler, id_victima, victima_victima)

        msg_victima = "S'ha confirmat la mort, gràcies per participar!"
        bot.send_message(id_victima, msg_victima)

        name_bandoler = f.execute_db(f.name_or_surname, id_bandoler)
        name_victima = f.execute_db(f.name_or_surname, id_victima)

        msg_bandoler = "S'ha confirmat la teva kill!\n"
        msg_participants = f"{name_bandoler} ha enxampat a {name_victima}! ACS🔫🕊"

        bot.send_message(id_bandoler, msg_bandoler)
        send_message_to_target('Tots els usuaris', msg_participants)
        bot.send_message(ADMIN_ID, msg_participants)
        n_bandolers = f.execute_db(f.n_bandolers)
        if n_bandolers > 1:
            msg_participants = f"Queden {n_bandolers} bandolers en joc🏜"
            send_message_to_target('Tots els usuaris', msg_participants)
            bot.send_message(ADMIN_ID, msg_participants)

        # Comprovar que la victima no sigui ell mateix
        if id_bandoler == victima_victima:
            winning_message(id_bandoler)

        else:
            msg_bandoler = "S'ha actualitzat la teva víctima.\n"
            msg_bandoler += "Per veure el seu perfil prem /victima."
            bot.send_message(id_bandoler, msg_bandoler)

@bot.message_handler(commands=['denegar'])
def deny_kill(message) -> None:
    if not f.execute_db(f.id_in_db, message.from_user.id):
        bot.send_message(message.chat.id, f.missatge_no_inscrits())
        return
    if not f.execute_db(f.is_pending, message.from_user.id):
        msg = "No tens cap enxampament pendent."
        bot.send_message(message.chat.id, msg)
    else:
        id_victima = message.from_user.id
        id_bandoler = f.execute_db(f.killer, id_victima)

        f.execute_db(f.update, 'estat', id_victima, 'jugant') 
        msg_bandoler = "Mort no confirmada. No juguis amb foc!"
        msg_victima = "L'enxampament ha estat denegat. Pots tornar a jugar amb normalitat.\n"
        bot.send_message(id_bandoler, msg_bandoler)
        bot.send_message(id_victima, msg_victima)

def winning_message(id_winner: int) -> None:
    """
    Envia missatge de guanyador a tots els participants + el missatge de la Nyacapada.
    """
    f.execute_db(f.update, 'estat', id_winner, 'mort') # TODO: en un futur fer estat guanyador
    f.execute_db(f.update, 'victima', id_winner, None)
    f.execute_db(f.set_winner, id_winner)
    msg_bandoler = "\n\nFELICITATS! Ets l'últim bandoler en joc!"
    msg_bandoler += "\nEl @SheriffDeDosrius es posarà amb contacte amb tu per coordinar la teva recompensa!"
    msg_bandoler += "\n\nEt posem en estat de mort per conveniència del programa, però no ho dubtis, has guanyat tu!!!"
    msg_bandoler += "\n\nGràcies per participar!"

    name_winner = f.execute_db(f.name_or_surname, id_winner)
    msg_participants = f"\n\nATENCIÓ: Tenim l'últim bandoler en joc, felicitats {name_winner}!!!"

    # Enviar la foto de l'últim bandoler + missatge a tots els participants
    picture_winner = f.execute_db(f.get_picture, id_winner)
    for user_id in f.execute_db(f.get_all_users):
        f.blob_to_image(picture_winner, bot, user_id, msg_participants)
    f.blob_to_image(picture_winner, bot, ADMIN_ID, msg_participants)

    bot.send_message(id_winner, msg_bandoler)

    msg_participants = "Anunciem els resultats de la Nyacapada:"
    msg_participants += f"\n\nEnhorabona {f.execute_db(f.get_nucli, id_winner).upper()}, heu guanyat 4 punts per tenir l'últim bandoler viu!"
    msg_participants += f"\n\nEnhorabona {f.execute_db(f.ranquing_nuclis)[0][0].upper()}, heu guanyat 4 punts per tenir la màxima participació al joc ({f.execute_db(f.ranquing_nuclis)[0][1]})!"
    msg_participants += "\n\nGràcies a tothom per participar! Ens veiem l'any que ve!"
    send_message_to_target('Tots els usuaris', msg_participants)
    bot.send_message(ADMIN_ID, msg_participants)

@bot.message_handler(commands=['ranquing_nuclis'])
def nuclis_rank(message):
    ranquing = f.execute_db(f.ranquing_nuclis)
    msg = "Ranquing de participants per nucli:\n\n"
    for i, nucli in enumerate(ranquing):
        msg += f"{i+1}. {nucli[0]}: {nucli[1]} participants\n"
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['ranquing_bandolers'])
def bandolers_rank(message):
    if f.execute_db(f.get_inscripcio_disponible):
        bot.send_message(message.chat.id, "No es pot mostrar el ranquing perquè encara no ha començat el joc.")
        return
    ranquing = f.execute_db(f.ranquing_bandolers)

    if len(ranquing) == 0:
        bot.send_message(message.chat.id, "Encara no hi ha hagut cap kill.")
        return

    msg = "Ranquing de bandolers amb més kills:\n\n"
    for i, bandoler in enumerate(ranquing):
        if bandoler[1] != '':
            msg += f"{i+1}. {bandoler[1]}: {bandoler[2]} kills\n"
        else:
            msg += f"{i+1}. {bandoler[0]}: {bandoler[2]} kills\n"
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['cementiri'])
def cementiri(message):
    cementiri_bandolers = f.execute_db(f.graveyard)
    msg = "Cementiri de bandolers:\n\n"

    # ensenya sobrenom o nom al la resta d'usuaris
    for i, id in enumerate(cementiri_bandolers):
        name_user = f.execute_db(f.name_or_surname, id)
        msg += f"{i+1}. {name_user}\n"
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['assignar_victimes'])
def assignar_victimes(message) -> None:
    if not f.is_admin(message):
        bot.send_message(message.chat.id, "No tens permisos per executar aquesta comanda.")
        return

    f.execute_db(f.assign_victims_cyclic, timeout=20)
    msg_admin = "S'han assignat les víctimes de manera cíclica.\n\n"
    msg_admin += "Per veure el cicle prem /cicle_bandolers."
    bot.send_message(ADMIN_ID, msg_admin)

@bot.message_handler(commands=['kill_bot'])
def kill_bot(message) -> None:
    if f.is_admin(message): 
        msg = "Estas segur que vols parar el bot?"
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)  
        markup.add('Sí', 'No')
        message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)
        bot.register_next_step_handler(message, confirm_kill_bot) 

def confirm_kill_bot(message) -> None:
    if message.text == 'Sí':
        msg = "Es pararà el bot al escriure qualsevol cosa per teclat."
        bot.send_message(ADMIN_ID, msg)
        bot.stop_polling()

    elif message.text == 'No':
        msg = "No s'ha parat el bot."
        bot.send_message(ADMIN_ID, msg)
    else:
        msg = "Opció no vàlida. Torna a intentar-ho."
        bot.send_message(ADMIN_ID, msg)
        bot.register_next_step_handler(message, confirm_kill_bot)

@bot.message_handler(commands=['comprobar_dades_usuaris'])
def check_dades_usuaris(message) -> None:
    if not f.is_admin(message):
        bot.send_message(message.chat.id, "No tens permisos per executar aquesta comanda.")
        return

    if f.execute_db(f.comprobar_dades_usuaris, message, bot):
        bot.send_message(ADMIN_ID, "Tots els usuaris estan ben registrats.")
    else:
        bot.send_message(ADMIN_ID, "Hi ha usuaris que no estan ben registrats. Comprova les dades i torna-ho a intentar.")

@bot.message_handler(commands=['tancar_inscripcions'])
def tancar_inscripcions(message) -> None:
    if f.is_admin(message):
        valor = f.execute_db(f.get_inscripcio_disponible)
        if valor:
            f.execute_db(f.change_inscripcio_disponible)
            msg = "Les inscripcions s'han tancat. Recorda començar el joc amb /comencar_joc.\n"
        else:
            msg = "Les inscripcions ja estan tancades.\n"
        bot.send_message(ADMIN_ID, msg)
        

@bot.message_handler(commands=['obrir_inscripcions'])
def obrir_inscripcions(message) -> None:
    if f.is_admin(message):
        valor = f.execute_db(f.get_inscripcio_disponible)
        if not valor:
            f.execute_db(f.change_inscripcio_disponible)
            msg = "Les inscripcions s'han obert. Ara els usuaris poden registrar-se.\n"
        else:
            msg = "Les inscripcions ja estan obertes.\n"
        bot.send_message(ADMIN_ID, msg)

@bot.message_handler(commands=['get_ids'])
def get_ids(message) -> None:
    if f.is_admin(message):
        for user_id in f.execute_db(f.get_all_users):
            user = f.execute_db(f.get_names, user_id)  # Obtenir dades de l'usuari
            if user[1] != '':
                msg = f"{user[0]} aka {user[1]} té ID {user_id}"
            else:
                msg = f"{user[0]} té ID {user_id}"
            bot.send_message(ADMIN_ID, msg)

@bot.message_handler(commands=['text'])
def text(message) -> None:
    if f.is_admin(message):
        msg = "Introdueix el text que vols enviar:\n"
        bot.send_message(ADMIN_ID, msg)
        bot.register_next_step_handler(message, choose_text_target)

def choose_text_target(message) -> None:
    if f.is_admin(message):
        text = message.text
        if text:
            markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
            markup.add('Bandolers', 'Enxampats', 'Pendents', 'Tots els usuaris', 'Cancel·lar')
            for user in f.execute_db(f.get_all_users):
                markup.add(f.execute_db(f.get_name,user))
            msg = "A qui vols enviar el missatge?\n"
            message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)
            bot.register_next_step_handler(message, lambda m: send_message_to_target(m, text))


def send_message_to_target(message, text: str) -> None:
    if type(message) is str:
        target = message
    else:
        target = message.text

        if not f.is_admin(message):
            msg = "No tens permisos per enviar missatges a tots els usuaris."
            bot.send_message(message.from_user.id, msg)
            return

    if text:
        match target:
            case 'Bandolers':
                users = f.execute_db(f.get_all_bandolers)
            case 'Enxampats':
                users = f.execute_db(f.get_all_enxampats)
            case 'Pendents':
                users = f.execute_db(f.get_all_pending)
            case 'Tots els usuaris':
                users = f.execute_db(f.get_all_users)
            case 'Cancel·lar':
                msg = "Enviament de missatge cancel·lat."
                bot.send_message(ADMIN_ID, msg)
                return
            case _:
                users = [f.execute_db(f.get_user_id_by_name, target)]

        for user_id in users:
            bot.send_message(user_id, text, reply_markup=ReplyKeyboardRemove())
        msg = f"Missatge enviat a {target}."
        bot.send_message(ADMIN_ID, msg)

@bot.message_handler(commands=['update_user'])
def select_user_to_update(message) -> None:
    if f.is_admin(message):
        # Botons per seleccionar usuari
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
        for user in f.execute_db(f.get_all_users):
            markup.add(f"{user}")  # Mostrar ID de l'usuari
        markup.add('cancelar')  # Afegir opció per cancel·lar
        msg = "Selecciona l'usuari que vols actualitzar:\n"
        message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)  
        bot.register_next_step_handler(message, update_user)

def update_user(message) -> None:
    if f.is_admin(message):
        # user_name = message.text
        # user_id = f.get_user_id_by_name(user_name)
        user_id = message.text
        if f.execute_db(f.id_in_db, user_id):
            markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
            markup.add('nom', 'sobrenom', 'descripcio', 'estat', 'nucli', 'victima', 'kills', 'cancelar')
            msg = f"Quin camp vols actualitzar per {user_id}?\n"
            message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)  
            bot.register_next_step_handler(message, lambda m: update_field(m, user_id))
        
        elif user_id == 'cancelar':
            msg = "Actualització cancel·lada."
            bot.send_message(ADMIN_ID, msg)
        else:
            msg = "Usuari no trobat."
            bot.send_message(ADMIN_ID, msg)

def update_field(message, user_id) -> None:
    if f.is_admin(message):
        field = message.text.strip().lower()  # Normalitzar el camp a minúscules
        if field in ['nom', 'sobrenom', 'descripcio', 'estat', 'nucli', 'victima', 'kills']:
            msg = f"Introdueix el nou valor per al camp {field}:\n"
            bot.send_message(ADMIN_ID, msg)
            bot.register_next_step_handler(message, lambda m: update_value(m, field, user_id))
        elif field == 'cancelar':
            msg = "Actualització cancel·lada."
            bot.send_message(ADMIN_ID, msg)
        else:
            msg = "Camp no vàlid."
            bot.send_message(ADMIN_ID, msg)

def update_value(message, field, user_id) -> None:
    if f.is_admin(message):
        value = message.text
        if field == 'kills' or field == 'victima':
            try:
                value = int(value)
            except ValueError:
                msg = f"El valor de {field} ha de ser un número enter."
                bot.send_message(ADMIN_ID, msg)
                return
        elif field == 'nucli':
            if value not in ['Dosrius', 'Canyamars', 'Can Massuet']:
                msg = "El nucli ha de ser 'Dosrius', 'Canyamars' o 'Can Massuet'."
                bot.send_message(ADMIN_ID, msg)
                return
        elif field == 'estat':
            if value not in ['jugant', 'mort', 'pendent']:
                msg = "L'estat ha de ser 'jugant', 'mort' o 'pendent'."
                bot.send_message(ADMIN_ID, msg)
                return
        
        f.execute_db(f.update, field, user_id, value)
        msg = f"Camp {field} actualitzat correctament per l'usuari {f.execute_db(f.get_name, user_id)} ({user_id})."
        bot.send_message(ADMIN_ID, msg)

@bot.message_handler(commands=['cicle_bandolers'])
def cicle_bandolers(message) -> None:
    if f.is_admin(message) and not f.execute_db(f.get_inscripcio_disponible):
        bot.send_message(ADMIN_ID, f.execute_db(f.text_cycle))
    else:
        msg = "No es pot mostrar el cicle perquè o les inscripcions seguèixen obertes o no ets admin..."
        bot.send_message(ADMIN_ID, msg)

@bot.message_handler(commands=['restart_db'])
def restart_data_base(message) -> None:
    if f.is_admin(message):
        msg = "Estas segur que vols reiniciar la base de dades?"
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)  
        markup.add('Sí', 'No')
        message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)
        bot.register_next_step_handler(message, confirm_restart_db)

def confirm_restart_db(message) -> None:
    if f.is_admin(message):
        if message.text != 'Sí':
            msg = "No s'ha reiniciat la base de dades."
            bot.send_message(ADMIN_ID, msg)
            return
        f.execute_db(f.restart_db)
        msg = "Base de dades reiniciada correctament."
        bot.send_message(ADMIN_ID, msg)

@bot.message_handler(commands=['matar'])
def matar(message) -> None:
    if f.is_admin(message):
        # Botons per seleccionar usuari 
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
        for user in f.execute_db(f.get_all_bandolers):
            markup.add(f"{f.execute_db(f.get_name, user)}")
        msg = "Selecciona l'usuari que vols matar:\n"
        message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)
        bot.register_next_step_handler(message, are_you_sure_kill)

def are_you_sure_kill(message) -> None:
    if f.is_admin(message):
        user_name = message.text
        user_id = f.execute_db(f.get_user_id_by_name, user_name)
        f.execute_db(f.show_user, user_id, bot, ADMIN_ID)
        msg = "Estas segur que vols eliminar aquest usuari del joc?"
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)  
        markup.add('Sí', 'No')
        message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)
        bot.register_next_step_handler(message, lambda m: select_victima(m, user_name))

def select_victima(message, user_name) -> None:
    if f.is_admin(message):
        if message.text == 'No':
            msg = "Operació cancel·lada."
            bot.send_message(ADMIN_ID, msg)
            return
        #print(f"Usuari seleccionat: {user_name}")
        id_user = f.execute_db(f.get_user_id_by_name, user_name)
        if id_user is None or not f.execute_db(f.id_in_db, id_user):
            msg = "Usuari no trobat o no registrat."
            bot.send_message(ADMIN_ID, msg)
            return
        
        msg = f"Selecciona motiu de la mort de l'usuari"
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
        markup.add('Fugitiu', 'Altres causes', 'Cancelar')

        message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)
        bot.register_next_step_handler(message, lambda m: choose_killing_motive(m, id_user))
    
    def choose_killing_motive(message, id_user) -> None:
        if f.is_admin(message):
            if message.text == 'Cancelar':
                msg = "Operació cancel·lada."
                bot.send_message(ADMIN_ID, msg)
                return
            elif message.text == 'Fugitiu':
                reason = 'fugitiu'
            else:
                reason = 'altres causes'
                msg = "Escriu el motiu de la mort de l'usuari:\n"
                bot.send_message(ADMIN_ID, msg)
                bot.register_next_step_handler(message, lambda m: kill_user(m, id_user, reason))
        
    def kill_user(message, id_user, reason) -> None:
        if f.is_admin(message):
            if reason == 'altres causes':
                motive = message.text
            else:
                motive = f"{name_user} ha estat declarat fugitiu per no presentar-se al mínim nombre de Control de Bandolers. El Sheriff l'ha declarat mort! ACS🔫🕊"

        name_user = f.execute_db(f.name_or_surname, id_user)
        killer = f.execute_db(f.killer, id_user)
        f.execute_db(f.kill, id_user) 

        send_message_to_target('Tots els usuaris', motive)
        bot.send_message(ADMIN_ID, motive)
        bot.send_message(id_user, "Gràcies per participar!")

        n_bandolers = f.execute_db(f.n_bandolers)
        if n_bandolers > 1:
            msg_participants = f"Queden {n_bandolers} bandolers en joc🏜"
            send_message_to_target('Tots els usuaris', msg_participants)
            bot.send_message(ADMIN_ID, msg_participants)

        victima = f.execute_db(f.get_victim, killer)
        # print(f"user: {id_user}, killer: {killer}, victima de killer: {victima}")
        if victima == killer:
            winning_message(killer)
        else:
            msg_killer = f"La teva víctima ha estat actualitzada. Pots veure la seva informació prement /victima."
            bot.send_message(killer, msg_killer)

@bot.message_handler(commands=['usuaris'])
def usuaris(message) -> None:
    if f.is_admin(message):

        msg = "Quins usuaris vols veure?\n"
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)  
        markup.add('Tots els usuaris', 'Bandolers', 'Enxampats', 'Pendents', 'Cancel·lar')
        message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)
        bot.register_next_step_handler(message, show_users)

def show_users(message) -> None:
    match message.text:
        case 'Bandolers':
            users = f.execute_db(f.get_all_bandolers)
        case 'Enxampats':
            users = f.execute_db(f.get_all_enxampats)
        case 'Pendents':
            users = f.execute_db(f.get_all_pending)
        case 'Tots els usuaris':
            users = f.execute_db(f.get_all_users)
        case 'Cancel·lar':
            bot.send_message(ADMIN_ID, "Operació cancel·lada.")
            return
        case _:
            bot.send_message(ADMIN_ID, "Opció no vàlida.")
            return

    if len(users)==0: 
        bot.send_message(ADMIN_ID, "No hi ha usuaris en aquest estat")
    else:
        for id in users:
            f.execute_db(f.show_user, id, bot, ADMIN_ID)

@bot.message_handler(commands=['regles_del_joc'])
def regles_del_joc(message) -> None:
    msg = f.file_content_2_string(f.get_path_messages("game_rules.txt"))
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['delete_user'])
def delete_user(message) -> None:
    if f.is_admin(message):
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
        for user in f.execute_db(f.get_all_users):
            markup.add(f"{f.execute_db(f.get_user, user)[0]}")
        markup.add('Cancel·lar')
        bot.send_message(ADMIN_ID, "Introdueix l'ID de l'usuari que vols eliminar:\n", reply_markup=markup)
        bot.register_next_step_handler(message, delete_user2)

def delete_user2(message) -> None:
    user_id = message.text
    if f.execute_db(f.id_in_db, user_id):
        f.execute_db(f.delete_user_from_db, user_id)
        msg = f"Usuari amb ID {user_id} eliminat correctament."
        bot.send_message(ADMIN_ID, msg)
    else:
        bot.send_message(ADMIN_ID, "Operació cancel·lada")

def update_state_and_kills_2_start(cursor: sqlite3.Cursor) -> None:
   for user in f.get_all_users(cursor):
       f.update(cursor, 'estat', user, 'jugant')
       f.update(cursor, 'kills', user, 0)


@bot.message_handler(commands=['comencar_joc'])
def començar_joc(message) -> None:
    if f.is_admin(message):
        f.execute_db(update_state_and_kills_2_start)
        f.execute_db(f.set_winner, 0)  # Resetejar guanyador
        # Tancar inscripcions
        if f.execute_db(f.get_inscripcio_disponible):
            f.execute_db(f.change_inscripcio_disponible)
        # Assignar víctimes
        assignar_victimes(message)
        msg_admin = "S'han posat a tots els usuaris com a jugant amb 0 kills i s'han assignat les víctimes.\n/usuaris per veure els usuaris registrats.\n\n"
        msg_admin += "El joc ha començat!"
        bot.send_message(ADMIN_ID, msg_admin)
        send_message_to_target('Tots els usuaris', f.file_content_2_string(f.get_path_messages("start.txt")))

@bot.message_handler(commands=['estat_bot'])
def estat_bot(message) -> None:
    if f.is_admin(message):
        msg = "Estat del bot:\n"
        msg += f"Inscripcions disponibles: {f.execute_db(f.get_inscripcio_disponible)}\n"
        msg += f"Guanyador: {f.execute_db(f.get_winner_from_var)}\n"
        msg += f"Usuaris registrats: {len(f.execute_db(f.get_all_users))}\n"
        msg += f"Usuaris jugant: {len(f.execute_db(f.get_all_bandolers))}\n"
        msg += f"Usuaris enxampats: {len(f.execute_db(f.get_all_enxampats))}\n"
        msg += f"Usuaris pendents: {len(f.execute_db(f.get_all_pending))}\n"
        msg += f"Usuaris registrats correctament : {f.execute_db(f.comprobar_dades_usuaris, message, bot)}\n"
        bot.send_message(ADMIN_ID, msg)

@bot.message_handler(commands=['send_automatic_winning_message'])
def send_winning_message(message) -> None:
    if f.is_admin(message):
        winner_id = f.execute_db(f.get_winner)
        if winner_id is None:
            bot.send_message(ADMIN_ID, "No hi ha cap guanyador.")
        else:
           winning_message(winner_id)

@bot.message_handler(commands=['send_winning_message_given_id'])
def send_winning_message_given_id(message) -> None:
    if f.is_admin(message):
        msg = "Introdueix l'ID del guanyador:\n"
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
        for user_id in f.execute_db(f.get_all_users):
            markup.add(f"{user_id}")
        markup.add('Cancel·lar')
        bot.send_message(ADMIN_ID, msg, reply_markup=markup)
        bot.register_next_step_handler(message, lambda m: send_winning_message_by_id(m))

def send_winning_message_by_id(message) -> None:
    if f.is_admin(message):
        user_id = message.text
        if user_id == 'Cancel·lar':
            bot.send_message(ADMIN_ID, "Operació cancel·lada.")
            return
        if f.execute_db(f.id_in_db, user_id):
            # show user info to admin
            f.execute_db(f.show_user, user_id, bot, ADMIN_ID)
            msg = f"Vols que guanyi aquesta persona?"
            markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
            markup.add('Sí', 'No')
            message = bot.send_message(ADMIN_ID, msg, reply_markup=markup)
            bot.register_next_step_handler(message, lambda m: confirm_winner(m, user_id))

def confirm_winner(message, user_id) -> None:
    if f.is_admin(message):
        if message.text == 'Sí':
            bot.send_message(ADMIN_ID, "Enviant missatge de guanyador...")
            winning_message(user_id)
        else:
            bot.send_message(ADMIN_ID, "Operació cancel·lada.")

@bot.message_handler(commands=['editar_perfil'])
def edit_profile(message):
    if not f.execute_db(f.id_in_db, message.from_user.id):
        bot.send_message(message.chat.id, f.missatge_no_inscrits())
        return
    if not f.execute_db(f.get_inscripcio_disponible):
        bot.send_message(message.chat.id, "El joc ha començat, ja no pots editar el teu perfil.")
        return
    msg = "Quin camp vols actualitzar?\n"
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, input_field_placeholder="Prem un botó", resize_keyboard=True)
    markup.add('nom', 'sobrenom', 'descripcio', 'nucli', 'foto', 'cancel·lar')
    message = bot.send_message(message.chat.id, msg, reply_markup=markup)
    bot.register_next_step_handler(message, edit_profile2)

def edit_profile2(message):
    field = message.text.strip().lower()  # Normalitzar el camp a minúscules
    match field:
        case 'nom' | 'sobrenom' | 'descripcio' | 'nucli':
            msg = f"Introdueix el nou valor per {field}:"
            bot.send_message(message.chat.id, msg)
            bot.register_next_step_handler(message, lambda m: edit_profile3(m, field))
        case 'foto':
            msg = "Envia la nova foto:"
            bot.send_message(message.chat.id, msg)
            bot.register_next_step_handler(message, lambda m: edit_profile3(m, field))
        case 'cancel·lar':
            msg = "Actualització cancel·lada."
            bot.send_message(message.chat.id, msg)
        case _:
            msg = "Camp no vàlid, operació cancel·lada."
            bot.send_message(message.chat.id, msg)

def edit_profile3(message, field):
    value = message.text
    match field:
        case 'nom' | 'sobrenom' | 'descripcio':
            if not f.assert_no_bar(value):
                msg = "El text no pot contenir el caràcter '/' . Operació cancel·lada."
                bot.send_message(message.chat.id, msg)
                return
            f.execute_db(f.update, field, message.from_user.id, value)
            msg = f"Camp {field} actualitzat correctament!\n"
            msg += "Per veure el teu perfil prem /perfil.\n"
            bot.send_message(message.chat.id, msg)
        case 'nucli':
            if value not in ['Dosrius', 'Canyamars', 'Can Massuet']:
                msg = "El nucli ha de ser 'Dosrius', 'Canyamars' o 'Can Massuet'. Operació cancel·lada."
                bot.send_message(message.chat.id, msg)
                return
        case 'foto':
            if message.content_type == 'photo':  # Comprova si el missatge conté una foto
                file_id = message.photo[-1].file_id  # L'últim element té la millor qualitat
                file_info = bot.get_file(file_id)
                file_path = file_info.file_path
                file_data = bot.download_file(file_path)

                # Guardar la imatge com un blob a la base de dades
                f.execute_db(f.update, 'foto', message.from_user.id, sqlite3.Binary(file_data))
                msg = "Foto actualitzada correctament!\n"
                msg += "Per veure el teu perfil prem /perfil.\n"
                bot.send_message(message.chat.id, msg)
        case _:
            msg = "Operació cancel·lada."
            bot.send_message(message.chat.id, msg)
