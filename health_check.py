import os
import sys
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.help import GetNearestDcRequest
from defunc import getoptions, list_sessions


def validate_api_credentials(api_id_str: str, api_hash_str: str) -> tuple[bool, list[str]]:
    problems: list[str] = []
    ok = True
    try:
        _ = int(api_id_str)
    except Exception:
        ok = False
        problems.append("API_ID должен быть числом")
    if not api_hash_str or len(api_hash_str) != 32 or not all(ch in '0123456789abcdef' for ch in api_hash_str.lower()):
        ok = False
        problems.append("API_HASH должен быть 32-символьной hex-строкой")
    return ok, problems


def check_api(api_id: int, api_hash: str) -> tuple[bool, str]:
    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        client.connect()
        # Лёгкий запрос, не требующий авторизации пользователя
        _ = client(GetNearestDcRequest())
        return True, "API доступен"
    except Exception as exc:
        return False, f"API ошибка: {exc}"
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


def check_sessions(api_id: int, api_hash: str) -> list[dict]:
    results: list[dict] = []
    sessions = list_sessions()
    for s in sessions:
        name = s.replace('\n', '')
        info = {"session": name, "authorized": False, "user": None, "error": None}
        client = TelegramClient(name, api_id, api_hash)
        try:
            client.connect()
            if client.is_user_authorized():
                me = client.get_me()
                info["authorized"] = True
                if me:
                    info["user"] = f"{getattr(me, 'username', None) or me.id}"
            else:
                info["authorized"] = False
        except Exception as exc:
            info["error"] = str(exc)
        finally:
            try:
                client.disconnect()
            except Exception:
                pass
        results.append(info)
    return results


def main() -> int:
    load_dotenv()
    options = getoptions()
    api_id_str = options[0].strip()
    api_hash_str = options[1].strip()

    if api_id_str == 'NONEID' or api_hash_str == 'NONEHASH':
        print("[FAIL] API_ID/API_HASH не настроены. Заполните .env или через меню настроек.")
        return 2

    ok_fmt, problems = validate_api_credentials(api_id_str, api_hash_str)
    if not ok_fmt:
        print("[FAIL] Неверный формат API_ID/API_HASH:")
        for p in problems:
            print(" -", p)
        return 2

    api_id = int(api_id_str)
    api_hash = api_hash_str

    api_ok, api_msg = check_api(api_id, api_hash)
    print(f"[API] {api_msg}")
    if not api_ok:
        return 2

    sess_results = check_sessions(api_id, api_hash)
    if not sess_results:
        print("[SESSIONS] .session файлов не найдено в корне проекта.")
        print("[HINT] Добавьте сессию через настройки (пункт 5) или положите .session файл в /workspace/")
        # API ок, но аккаунт не привязан
        return 3

    any_ok = False
    for r in sess_results:
        if r["error"]:
            print(f"[SESSION] {r['session']}: ошибка — {r['error']}")
            continue
        if r["authorized"]:
            any_ok = True
            print(f"[SESSION] {r['session']}: авторизован ✅ (user: {r['user']})")
        else:
            print(f"[SESSION] {r['session']}: не авторизован ❌")

    if any_ok:
        print("[OK] API работает и хотя бы одна сессия авторизована.")
        return 0
    else:
        print("[WARN] API работает, но нет авторизованных сессий.")
        return 3


if __name__ == '__main__':
    sys.exit(main())

