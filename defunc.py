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
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env if present
load_dotenv()

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


def _env_path() -> str:
    """Locate .env file path or propose default in current working directory."""
    located = find_dotenv(usecwd=True)
    if located:
        return located
    return os.path.join(os.getcwd(), '.env')


def _read_bool_env(var_name: str, default: bool) -> bool:
    val = os.getenv(var_name)
    if val is None:
        return default
    return str(val).strip().lower() in ('1', 'true', 'yes', 'y', 'on')


def _write_env_values(updates: dict):
    """Idempotently upsert key=value pairs into .env file."""
    path = _env_path()
    existing: dict[str, str] = {}
    lines: list[str] = []
    if os.path.exists(path):
        with open(path, 'r') as f:
            lines = f.readlines()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in stripped:
                continue
            k, v = stripped.split('=', 1)
            existing[k.strip()] = v
    existing.update({k: str(v) for k, v in updates.items()})
    # Rebuild preserving non-assignment lines, and updating assignments
    output_lines: list[str] = []
    written_keys: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            output_lines.append(line)
            continue
        k, _ = stripped.split('=', 1)
        k = k.strip()
        if k in existing:
            output_lines.append(f"{k}={existing[k]}\n")
            written_keys.add(k)
        else:
            output_lines.append(line)
    # Append any new keys
    for k, v in existing.items():
        if k not in written_keys:
            output_lines.append(f"{k}={v}\n")
    with open(path, 'w') as f:
        f.writelines(output_lines)


def config():
    """Interactive configuration that writes API_ID/API_HASH and toggles into .env."""
    while True:
        os.system('cls||clear')

        # Ensure auxiliary files exist
        if not os.path.exists('usernames.txt'):
            open('usernames.txt', 'a').close()
        if not os.path.exists('userids.txt'):
            open('userids.txt', 'a').close()

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
                          "6 - Сбросить настройки (.env)\n"
                          "e - Выход\n"
                          "Ввод: ")
                    ))

        if key == '1':
            os.system('cls||clear')
            new_api_id = str(input("Введите API_ID: ")).strip()
            _write_env_values({"API_ID": new_api_id})

        elif key == '2':
            os.system('cls||clear')
            new_api_hash = str(input("Введите API_HASH: ")).strip()
            _write_env_values({"API_HASH": new_api_hash})

        elif key == '3':
            # toggle PARSE_USER_ID
            current = _read_bool_env('PARSE_USER_ID', True)
            _write_env_values({"PARSE_USER_ID": str(not current)})

        elif key == '4':
            # toggle PARSE_USER_NAME
            current = _read_bool_env('PARSE_USER_NAME', True)
            _write_env_values({"PARSE_USER_NAME": str(not current)})
        
        elif key == '5':
            os.system('cls||clear')
            api_id_str = options[0].replace('\n', '')
            api_hash_str = options[1].replace('\n', '')
            if api_id_str == "NONEID" or api_hash_str == "NONEHASH":
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
            client = TelegramClient(session_name, int(api_id_str), api_hash_str).start(phone)
            print(f"Создана сессия: {session_filename}")
            
        elif key == '6':
            os.system('cls||clear')
            answer = input("Вы уверены?\nAPI_ID и API_HASH будут удалены из .env\n"
                           "1 - Удалить\n2 - Назад\n"
                           "Ввод: ")
            if answer == '1':
                # Remove keys by rewriting without them
                _write_env_values({"API_ID": "", "API_HASH": ""})
                print("Настройки очищены.")
                time.sleep(2)
            else:
                continue

        elif key == 'e':
            os.system('cls||clear')
            break


def getoptions():
    """Return options in legacy list format, backed by environment variables.

    [0]: API_ID or "NONEID\n"
    [1]: API_HASH or "NONEHASH\n"
    [2]: 'True\n' or 'False\n' for PARSE_USER_ID
    [3]: 'True\n' or 'False\n' for PARSE_USER_NAME
    """
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')

    # Backward-compat: try to load from options.txt if env missing
    if (not api_id or not api_hash) and os.path.exists('options.txt'):
        try:
            with open('options.txt', 'r') as f:
                legacy = f.readlines()
            if len(legacy) >= 2:
                if not api_id and legacy[0].strip() and legacy[0].strip() != 'NONEID':
                    api_id = legacy[0].strip()
                if not api_hash and legacy[1].strip() and legacy[1].strip() != 'NONEHASH':
                    api_hash = legacy[1].strip()
        except Exception:
            pass

    parse_user_id = _read_bool_env('PARSE_USER_ID', True)
    parse_user_name = _read_bool_env('PARSE_USER_NAME', True)

    return [
        f"{api_id if api_id else 'NONEID'}\n",
        f"{api_hash if api_hash else 'NONEHASH'}\n",
        f"{'True' if parse_user_id else 'False'}\n",
        f"{'True' if parse_user_name else 'False'}\n",
    ]


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
    if index == 2:
        current = _read_bool_env('PARSE_USER_ID', True)
        _write_env_values({"PARSE_USER_ID": str(not current)})
    else:
        current = _read_bool_env('PARSE_USER_NAME', True)
        _write_env_values({"PARSE_USER_NAME": str(not current)})
    # Recompute options to reflect changes
    options = getoptions()
    return True, options
