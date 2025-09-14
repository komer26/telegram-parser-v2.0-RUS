'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import os
import sys
from telethon.sync import TelegramClient
from telethon import events
from defunc import (
	getoptions,
	list_sessions,
	list_groups_for_session,
	parse_session_group,
	invite_from_usernames,
	toggle_option,
)


def get_api_credentials():
	options = getoptions()
	if not options or options[0] == "NONEID\n" or options[1] == "NONEHASH\n":
		raise RuntimeError("API_ID/API_HASH are not configured. Run the app once and set them in settings.")
	api_id = int(options[0].replace('\n', ''))
	api_hash = str(options[1].replace('\n', ''))
	return api_id, api_hash


def is_allowed_user(sender_id: int) -> bool:
	owner_id_env = os.getenv('BOT_OWNER_ID')
	if not owner_id_env:
		return True
	try:
		owner_id = int(owner_id_env)
	except ValueError:
		return True
	return sender_id == owner_id


HELP_TEXT = (
	"Команды:\n"
	"/start - помощь\n"
	"/sessions - список .session\n"
	"/groups <s_idx> - группы аккаунта\n"
	"/parse <s_idx> <g_idx|all> - парсить группу или все\n"
	"/invite <s_idx> <channel> [limit] - инвайт из usernames.txt\n"
	"/toggle_id - вкл/выкл парсинг user-id\n"
	"/toggle_name - вкл/выкл парсинг user-name\n"
	"/clear - очистить usernames.txt и userids.txt\n"
	"/config - показать текущие настройки"
)


def main():
	try:
		api_id, api_hash = get_api_credentials()
	except Exception as exc:
		print(f"[bot] Ошибка конфигурации: {exc}")
		sys.exit(1)

	bot_token = os.getenv('BOT_TOKEN')
	if not bot_token:
		print("[bot] Переменная окружения BOT_TOKEN не задана")
		sys.exit(1)

	client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)

	@client.on(events.NewMessage(pattern=r'^/start$'))
	async def start_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		await event.respond(HELP_TEXT)

	@client.on(events.NewMessage(pattern=r'^/sessions$'))
	async def sessions_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		sessions = list_sessions()
		if not sessions:
			await event.respond('Нет .session файлов в директории.')
			return
		text_lines = [f"[{idx}] {name}" for idx, name in enumerate(sessions)]
		await event.respond("Сессии:\n" + "\n".join(text_lines))

	@client.on(events.NewMessage(pattern=r'^/groups\s+(\d+)$'))
	async def groups_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		try:
			s_idx = int(event.pattern_match.group(1))
		except Exception:
			await event.respond('Формат: /groups <s_idx>')
			return
		sessions = list_sessions()
		if s_idx < 0 or s_idx >= len(sessions):
			await event.respond('Неверный индекс сессии')
			return
		try:
			groups = list_groups_for_session(sessions[s_idx], api_id, api_hash)
		except Exception as exc:
			await event.respond(f'Ошибка получения групп: {exc}')
			return
		if not groups:
			await event.respond('Группы не найдены')
			return
		text_lines = [f"[{idx}] {title} @{username}" if username != '-' else f"[{idx}] {title}"
					 for idx, title, username in groups]
		await event.respond("Группы:\n" + "\n".join(text_lines))

	@client.on(events.NewMessage(pattern=r'^/parse\s+(\d+)\s+(\d+|all)$'))
	async def parse_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		parts = event.raw_text.split()
		if len(parts) != 3:
			await event.respond('Формат: /parse <s_idx> <g_idx|all>')
			return
		sessions = list_sessions()
		try:
			s_idx = int(parts[1])
		except Exception:
			await event.respond('Неверный индекс сессии')
			return
		if s_idx < 0 or s_idx >= len(sessions):
			await event.respond('Неверный индекс сессии')
			return
		g_arg = parts[2]
		group_index = None if g_arg == 'all' else int(g_arg)
		options = getoptions()
		parse_user_id = options[2] == 'True\n'
		parse_user_name = options[3] == 'True\n'
		try:
			result = parse_session_group(
				sessions[s_idx], api_id, api_hash, group_index, parse_user_id, parse_user_name
			)
		except Exception as exc:
			await event.respond(f'Ошибка парсинга: {exc}')
			return
		await event.respond(f'Готово: {result}')

	@client.on(events.NewMessage(pattern=r'^/invite\s+(\d+)\s+(@?[A-Za-z0-9_]+)(?:\s+(\d+))?$'))
	async def invite_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		parts = event.raw_text.split()
		if len(parts) < 3:
			await event.respond('Формат: /invite <s_idx> <channel> [limit]')
			return
		sessions = list_sessions()
		try:
			s_idx = int(parts[1])
		except Exception:
			await event.respond('Неверный индекс сессии')
			return
		if s_idx < 0 or s_idx >= len(sessions):
			await event.respond('Неверный индекс сессии')
			return
		channel_username = parts[2]
		if channel_username.startswith('@'):
			channel_username = channel_username[1:]
		max_invites = int(parts[3]) if len(parts) >= 4 else 20
		try:
			count = invite_from_usernames(sessions[s_idx], api_id, api_hash, channel_username, max_invites)
		except Exception as exc:
			await event.respond(f'Ошибка инвайта: {exc}')
			return
		await event.respond(f'Инвайтов отправлено: {count}')

	@client.on(events.NewMessage(pattern=r'^/toggle_id$'))
	async def toggle_id_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		ok, options = toggle_option(2)
		if not ok:
			await event.respond('Не удалось переключить опцию')
			return
		await event.respond(f"parse user-id: {options[2].strip()}")

	@client.on(events.NewMessage(pattern=r'^/toggle_name$'))
	async def toggle_name_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		ok, options = toggle_option(3)
		if not ok:
			await event.respond('Не удалось переключить опцию')
			return
		await event.respond(f"parse user-name: {options[3].strip()}")

	@client.on(events.NewMessage(pattern=r'^/clear$'))
	async def clear_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		open('usernames.txt', 'w').close()
		open('userids.txt', 'w').close()
		await event.respond('Очищено usernames.txt и userids.txt')

	@client.on(events.NewMessage(pattern=r'^/config$'))
	async def config_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		options = getoptions()
		api_id_display = options[0].strip()
		hash_display = options[1].strip()
		await event.respond(
			f"API_ID: {api_id_display}\nAPI_HASH: {hash_display}\n"
			f"parse user-id: {options[2].strip()}\nparse user-name: {options[3].strip()}"
		)

	print('[bot] Бот запущен. Ожидаю команды...')
	client.run_until_disconnected()


if __name__ == '__main__':
	main()

