'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
import os
import time
import random

def inviting(client, channel, users):
    client(InviteToChannelRequest(
        channel=channel,
        users=[users]
    ))


def parsing(client, index: int, id: bool, name: bool):
    all_participants = []
    all_participants = client.get_participants(index)
    if name:
        with open('usernames.txt', 'r+') as f:
            usernames = f.readlines()
            for user in all_participants:
                if user.username:
                    if ('Bot' not in user.username) and ('bot' not in user.username):
                        if (('@' + user.username + '\n') not in usernames):
                            f.write('@' + user.username + '\n')
                        else:
                            continue
                    else:
                        continue
                else:
                    continue
    if id:
        with open('userids.txt', 'r+') as f:
            userids = f.readlines()
            for user in all_participants:
                if (str(user.id) + '\n') not in userids:
                    f.write(str(user.id) + '\n')


def config():
    while True:
        os.system('cls||clear')

        # Создаём файлы по умолчанию, если отсутствуют
        if not os.path.exists('options.txt'):
            with open('options.txt', 'w') as f:
                f.write("NONEID\nNONEHASH\nTrue\nTrue\n")
        if not os.path.exists('usernames.txt'):
            open('usernames.txt', 'a').close()
        if not os.path.exists('userids.txt'):
            open('userids.txt', 'a').close()

        with open('options.txt', 'r+') as f:
            if not f.readlines():
                f.write("NONEID\nNONEHASH\nTrue\nTrue\n")
                continue
                
        options = getoptions()
        sessions = []
        for file in os.listdir('.'):
            if file.endswith('.session'):
                sessions.append(file)

        key = str(input((f"1 - Обновить api_id [{options[0].replace('\n', '')}]\n"
                         f"2 - Обновить api_hash [{options[1].replace('\n', '')}]\n"
                         f"3 - Парсить user-id [{options[2].replace('\n', '')}]\n"
                         f"4 - Парсить user-name [{options[3].replace('\n', '')}]\n"
                         f"5 - Добавить аккаунт юзербота [{len(sessions)}]\n"
                          "6 - Сбросить настройки\n"
                          "e - Выход\n"
                          "Ввод: ")
                    ))

        if key == '1':
            os.system('cls||clear')
            options[0] = str(input("Введите API_ID: ")) + "\n"

        elif key == '2':
            os.system('cls||clear')
            options[1] = str(input("Введите API_HASH: ")) + "\n"

        elif key == '3':
            if options[2] == 'True\n':
                options[2] = 'False\n'
            else:
                options[2] = 'True\n'

        elif key == '4':
            if options[3] == 'True\n':
                options[3] = 'False\n'
            else:
                options[3] = 'True\n'
        
        elif key == '5':
            os.system('cls||clear')
            if options[0] == "NONEID\n" or options[1] == "NONEHASH\n":
                print("Проверьте api_id и api_hash")
                time.sleep(2)
                continue

            print("Аккаунты:\n")
            for i in sessions:
                print(i)

            # Запросить кастомное имя для .session файла
            while True:
                session_name = str(input("Введите имя сессии (латиница/цифры . _ -): ")).strip()
                if not session_name:
                    print("Имя не может быть пустым.")
                    continue
                allowed = "._-"
                valid = all(ch.isalnum() or ch in allowed for ch in session_name)
                if not valid:
                    print("Разрешены только буквы/цифры/._- без пробелов.")
                    continue
                if session_name.endswith('.session'):
                    session_filename = session_name
                else:
                    session_filename = session_name + '.session'
                if os.path.exists(session_filename):
                    print("Такое имя уже существует. Выберите другое.")
                    continue
                break

            phone = str(input("Введите номер телефона аккаунта: "))
            client = TelegramClient(session_name, int(options[0].replace('\n', '')),
                                    options[1].replace('\n', '')).start(phone)
            print(f"Создана сессия: {session_filename}")
            
        elif key == '6':
            os.system('cls||clear')
            answer = input("Вы уверены?\nAPI_ID и API_HASH будут удалены\n"
                           "1 - Удалить\n2 - Назад\n"
                           "Ввод: ")
            if answer == '1':    
                options.clear()
                print("Настройки очищены.")
                time.sleep(2)
            else:
                continue

        elif key == 'e':
            os.system('cls||clear')
            break

        with open('options.txt', 'w') as f:
            f.writelines(options)


def getoptions():
    with open('options.txt', 'r') as f:
        options = f.readlines()
    return options


# ===== Helpers for non-interactive (bot) control =====

def list_sessions() -> list:
    sessions = []
    for file in os.listdir('.'):
        if file.endswith('.session'):
            sessions.append(file)
    return sessions


def list_groups_for_session(session_file: str, api_id: int, api_hash: str):
    client = TelegramClient(session_file.replace('\n', ''), api_id, api_hash).start()
    chats = []
    groups = []
    result = client(GetDialogsRequest(
        offset_date=None,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=200,
        hash=0
    ))
    chats.extend(result.chats)
    for chat in chats:
        try:
            if chat.megagroup is True:
                groups.append(chat)
        except:
            continue
    # Return lightweight data: (index, title, username or '-')
    export = []
    for index, chat in enumerate(groups):
        username = getattr(chat, 'username', None)
        export.append((index, chat.title, username if username else '-'))
    return export


def parse_session_group(session_file: str, api_id: int, api_hash: str, group_index: int | None,
                        parse_user_id: bool, parse_user_name: bool) -> str:
    client = TelegramClient(session_file.replace('\n', ''), api_id, api_hash).start()
    chats = []
    groups = []
    result = client(GetDialogsRequest(
        offset_date=None,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=200,
        hash=0
    ))
    chats.extend(result.chats)
    for chat in chats:
        try:
            if chat.megagroup is True:
                groups.append(chat)
        except:
            continue

    if group_index is None:
        for g in groups:
            parsing(client, g, parse_user_id, parse_user_name)
        return 'parsed_all'
    else:
        if 0 <= group_index < len(groups):
            target_group = groups[group_index]
            parsing(client, target_group, parse_user_id, parse_user_name)
            return f'parsed_{group_index}'
        else:
            return 'invalid_index'


def invite_from_usernames(session_file: str, api_id: int, api_hash: str, channel_username: str,
                          max_invites: int = 20) -> int:
    client = TelegramClient(session_file.replace('\n', ''), api_id, api_hash).start()
    with open('usernames.txt', 'r') as f:
        users = [line.strip() for line in f if line.strip()]
    invited = 0
    for user in users[:max_invites]:
        try:
            inviting(client, channel_username, user)
            invited += 1
            time.sleep(random.randrange(15, 40))
        except Exception:
            break
    return invited


def toggle_option(index: int) -> tuple[bool, list]:
    options = getoptions()
    if index not in (2, 3):
        return False, options
    if options[index] == 'True\n':
        options[index] = 'False\n'
    else:
        options[index] = 'True\n'
    with open('options.txt', 'w') as f:
        f.writelines(options)
    return True, options
