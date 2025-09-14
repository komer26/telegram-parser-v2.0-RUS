'''
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
'''

import os
import sys
from telethon.sync import TelegramClient
from telethon import events, Button
from telethon.errors.rpcerrorlist import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
from defunc import (
	getoptions,
	list_sessions,
	list_groups_for_session,
	parse_session_group,
	parse_session_group_filtered,
	parse_session_group_active,
	parse_session_group_active_filtered,
	invite_from_usernames,
	invite_from_usernames_with_summary,
	toggle_option,
)
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


def get_api_credentials():
	options = getoptions()
	if not options or options[0] == "NONEID\n" or options[1] == "NONEHASH\n":
		raise RuntimeError("API_ID/API_HASH are not configured. Set them in .env or via settings.")
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
	"/add_session - добавить .session через бота\n"
	"/groups <s_idx> - группы аккаунта\n"
	"/parse <s_idx> <g_idx|all> - парсить группу или все\n"
	"/parse_active <s_idx> <g_idx|all> [limit] - парсить по отправителям сообщений\n"
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

	# Simple in-memory state for asking text input and filters
	user_states: dict[int, dict] = {}

	# ===== UI helpers =====
	def cb(*parts: object) -> bytes:
		return ('|'.join(str(p) for p in parts)).encode()

	async def show_main(event):
		buttons = [
			[Button.inline('Сессии', cb('SESS'))],
			[Button.inline('Добавить сессию', cb('SESS_ADD'))],
			[Button.inline('Опции', cb('OPT'))],
			[Button.inline('Очистить юзеров', cb('CLR'))],
			[Button.inline('Настройки', cb('CFG'))],
		]
		text = 'Выберите действие:'
		if isinstance(event, events.CallbackQuery.Event) or getattr(event, 'is_reply', False):
			try:
				await event.edit(text, buttons=buttons)
			except Exception:
				await event.respond(text, buttons=buttons)
		else:
			await event.respond(text, buttons=buttons)

	async def show_sessions(event):
		sessions = list_sessions()
		if not sessions:
			await event.edit('Нет .session файлов. Добавьте их в директорию проекта.', buttons=[[Button.inline('Назад', cb('MAIN'))]])
			return
		rows = []
		for idx, name in enumerate(sessions):
			rows.append([Button.inline(f'[{idx}] {name}', cb('SESS_SEL', idx))])
		rows.append([Button.inline('Назад', cb('MAIN'))])
		await event.edit('Сессии:', buttons=rows)

	async def show_session_menu(event, s_idx: int):
		sessions = list_sessions()
		if s_idx < 0 or s_idx >= len(sessions):
			await event.edit('Неверный индекс сессии', buttons=[[Button.inline('Назад', cb('SESS'))]])
			return
		name = sessions[s_idx]
		buttons = [
			[Button.inline('Группы', cb('GRP', s_idx, 0))],
			[Button.inline('Парсить все', cb('PARSE_ALL', s_idx))],
			[Button.inline('Парсить все (фильтр)', cb('PARSE_ALL_FILTERS', s_idx))],
			[Button.inline('Парсить активных', cb('PARSE_ACTIVE_ALL', s_idx))],
			[Button.inline('Парсить активных (фильтр)', cb('PARSE_ACTIVE_ALL_FILTERS', s_idx))],
			[Button.inline('Инвайт из usernames.txt', cb('INV', s_idx))],
			[Button.inline('Назад', cb('SESS'))],
		]
		await event.edit(f'Сессия: {name}', buttons=buttons)

	async def show_groups(event, s_idx: int, page: int = 0):
		sessions = list_sessions()
		if s_idx < 0 or s_idx >= len(sessions):
			await event.edit('Неверный индекс сессии', buttons=[[Button.inline('Назад', cb('SESS'))]])
			return
		all_groups = list_groups_for_session(sessions[s_idx], api_id, api_hash)
		per_page = 10
		start = page * per_page
		chunk = all_groups[start:start + per_page]
		rows = []
		for idx, title, username in chunk:
			label = f'[{idx}] {title}' if username == '-' else f'[{idx}] {title} @{username}'
			rows.append([
				Button.inline(label, cb('PARSE_ONE', s_idx, idx)),
				Button.inline('Фильтр', cb('PARSE_ONE_FILTERS', s_idx, idx)),
				Button.inline('Активные', cb('PARSE_ACTIVE_ONE', s_idx, idx)),
				Button.inline('Активные (фильтр)', cb('PARSE_ACTIVE_ONE_FILTERS', s_idx, idx)),
			])
		nav = []
		if start > 0:
			nav.append(Button.inline('⬅️', cb('GRP', s_idx, page - 1)))
		if start + per_page < len(all_groups):
			nav.append(Button.inline('➡️', cb('GRP', s_idx, page + 1)))
		if nav:
			rows.append(nav)
		rows.append([Button.inline('Назад', cb('SESS_SEL', s_idx))])
		await event.edit('Группы:', buttons=rows)

	@client.on(events.NewMessage(pattern=r'^/start$'))
	async def start_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		await show_main(event)

	@client.on(events.CallbackQuery)
	async def callbacks(event):
		if not is_allowed_user(event.sender_id):
			await event.answer('Недоступно', alert=True)
			return
		try:
			parts = event.data.decode().split('|')
		except Exception:
			await event.answer()
			return
		key = parts[0]
		if key == 'MAIN':
			await show_main(event)
		elif key == 'SESS':
			await show_sessions(event)
		elif key == 'SESS_SEL':
			s_idx = int(parts[1])
			await show_session_menu(event, s_idx)
		elif key == 'SESS_ADD':
			# Начало мастера добавления сессии
			user_states[event.sender_id] = {'action': 'add_session', 'step': 'ask_name', 'authorized': False}
			await event.edit('Введите имя сессии (латиница/цифры . _ -). Можно без .session', buttons=[[Button.inline('Отмена', cb('SESS_ADD_CANCEL'))]])
		elif key == 'SESS_ADD_CANCEL':
			st = user_states.get(event.sender_id)
			client2 = st.get('client') if st else None
			if client2:
				try:
					client2.disconnect()
				except Exception:
					pass
			session_filename = st.get('session_filename') if st else None
			if session_filename and not st.get('authorized'):
				try:
					os.remove(session_filename)
				except Exception:
					pass
			user_states.pop(event.sender_id, None)
			await event.edit('Отменено', buttons=[[Button.inline('Назад', cb('MAIN'))]])
		elif key == 'GRP':
			s_idx = int(parts[1]); page = int(parts[2])
			await show_groups(event, s_idx, page)
		elif key == 'PARSE_ONE':
			s_idx = int(parts[1]); g_idx = int(parts[2])
			options = getoptions()
			parse_user_id = options[2] == 'True\n'
			parse_user_name = options[3] == 'True\n'
			try:
				res = parse_session_group(list_sessions()[s_idx], api_id, api_hash, g_idx, parse_user_id, parse_user_name)
			except Exception as exc:
				await event.answer('Ошибка'); await event.edit(f'Ошибка: {exc}', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]]); return
			await event.edit(f'Готово: {res}', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]])
		elif key == 'PARSE_ONE_FILTERS':
			s_idx = int(parts[1]); g_idx = int(parts[2])
			user_states[event.sender_id] = {'action': 'parse_filters', 's_idx': s_idx, 'g_idx': g_idx, 'active': False}
			await event.edit('Фильтры: выберите вариант', buttons=[
				[Button.inline('Все', cb('F_ALL'))],
				[Button.inline('Без админов', cb('F_NOADM'))],
				[Button.inline('Онлайн <= 7 дней', cb('F_7'))],
				[Button.inline('Онлайн <= 14 дней', cb('F_14'))],
				[Button.inline('Онлайн <= 30 дней', cb('F_30'))],
				[Button.inline('Учитывать «Недавно» (вкл/выкл)', cb('F_REC'))],
				[Button.inline('Старт', cb('F_GO'))],
				[Button.inline('Назад', cb('SESS_SEL', s_idx))],
			])
		elif key == 'PARSE_ALL':
			s_idx = int(parts[1])
			options = getoptions()
			parse_user_id = options[2] == 'True\n'
			parse_user_name = options[3] == 'True\n'
			try:
				res = parse_session_group(list_sessions()[s_idx], api_id, api_hash, None, parse_user_id, parse_user_name)
			except Exception as exc:
				await event.edit(f'Ошибка: {exc}', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]]); return
			await event.edit(f'Готово: {res}', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]])
		elif key == 'PARSE_ALL_FILTERS':
			s_idx = int(parts[1])
			user_states[event.sender_id] = {'action': 'parse_filters', 's_idx': s_idx, 'g_idx': None, 'active': False}
			await event.edit('Фильтры: выберите вариант', buttons=[
				[Button.inline('Все', cb('F_ALL'))],
				[Button.inline('Без админов', cb('F_NOADM'))],
				[Button.inline('Онлайн <= 7 дней', cb('F_7'))],
				[Button.inline('Онлайн <= 14 дней', cb('F_14'))],
				[Button.inline('Онлайн <= 30 дней', cb('F_30'))],
				[Button.inline('Учитывать «Недавно» (вкл/выкл)', cb('F_REC'))],
				[Button.inline('Старт', cb('F_GO'))],
				[Button.inline('Назад', cb('SESS_SEL', s_idx))],
			])
		elif key == 'PARSE_ACTIVE_ONE':
			s_idx = int(parts[1]); g_idx = int(parts[2])
			options = getoptions()
			parse_user_id = options[2] == 'True\n'
			parse_user_name = options[3] == 'True\n'
			try:
				res = parse_session_group_active(list_sessions()[s_idx], api_id, api_hash, g_idx, parse_user_id, parse_user_name)
			except Exception as exc:
				await event.edit(f'Ошибка: {exc}', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]]); return
			await event.edit(f'Готово: {res}', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]])
		elif key == 'PARSE_ACTIVE_ALL':
			s_idx = int(parts[1])
			options = getoptions()
			parse_user_id = options[2] == 'True\n'
			parse_user_name = options[3] == 'True\n'
			try:
				res = parse_session_group_active(list_sessions()[s_idx], api_id, api_hash, None, parse_user_id, parse_user_name)
			except Exception as exc:
				await event.edit(f'Ошибка: {exc}', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]]); return
			await event.edit(f'Готово: {res}', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]])
		elif key == 'PARSE_ACTIVE_ONE_FILTERS':
			s_idx = int(parts[1]); g_idx = int(parts[2])
			user_states[event.sender_id] = {'action': 'parse_filters', 's_idx': s_idx, 'g_idx': g_idx, 'active': True}
			await event.edit('Фильтры: выберите вариант', buttons=[
				[Button.inline('Все', cb('F_ALL'))],
				[Button.inline('Без админов', cb('F_NOADM'))],
				[Button.inline('Онлайн <= 7 дней', cb('F_7'))],
				[Button.inline('Онлайн <= 14 дней', cb('F_14'))],
				[Button.inline('Онлайн <= 30 дней', cb('F_30'))],
				[Button.inline('Учитывать «Недавно» (вкл/выкл)', cb('F_REC'))],
				[Button.inline('Старт', cb('F_GO'))],
				[Button.inline('Назад', cb('SESS_SEL', s_idx))],
			])
		elif key == 'PARSE_ACTIVE_ALL_FILTERS':
			s_idx = int(parts[1])
			user_states[event.sender_id] = {'action': 'parse_filters', 's_idx': s_idx, 'g_idx': None, 'active': True}
			await event.edit('Фильтры: выберите вариант', buttons=[
				[Button.inline('Все', cb('F_ALL'))],
				[Button.inline('Без админов', cb('F_NOADM'))],
				[Button.inline('Онлайн <= 7 дней', cb('F_7'))],
				[Button.inline('Онлайн <= 14 дней', cb('F_14'))],
				[Button.inline('Онлайн <= 30 дней', cb('F_30'))],
				[Button.inline('Учитывать «Недавно» (вкл/выкл)', cb('F_REC'))],
				[Button.inline('Старт', cb('F_GO'))],
				[Button.inline('Назад', cb('SESS_SEL', s_idx))],
			])
		elif key in ('F_ALL','F_NOADM','F_7','F_14','F_30','F_REC','F_GO'):
			st = user_states.get(event.sender_id, {})
			if not st or st.get('action') != 'parse_filters':
				await event.answer(); return
			if key == 'F_REC':
				st['include_recently'] = not st.get('include_recently', True)
				user_states[event.sender_id] = st
				await event.answer(f"Недавно: {'Да' if st['include_recently'] else 'Нет'}", alert=False)
				return
			if key == 'F_ALL':
				st['exclude_admins'] = False; st['last_seen_days'] = None
			elif key == 'F_NOADM':
				st['exclude_admins'] = True
			elif key == 'F_7':
				st['last_seen_days'] = 7
			elif key == 'F_14':
				st['last_seen_days'] = 14
			elif key == 'F_30':
				st['last_seen_days'] = 30
			user_states[event.sender_id] = st
			if key != 'F_GO':
				await event.answer('Фильтр применён', alert=False)
				return
			# GO
			s_idx = int(st['s_idx']); g_idx = st['g_idx']; active = bool(st.get('active'))
			exclude_admins = bool(st.get('exclude_admins', False))
			last_seen_days = st.get('last_seen_days', None)
			include_recently = st.get('include_recently', True)
			options = getoptions()
			parse_user_id = options[2] == 'True\n'
			parse_user_name = options[3] == 'True\n'
			try:
				progress = {'processed': 0, 'total': 0}
				await event.edit(f"Старт... 0/0", buttons=[[Button.inline('Отмена', cb('SESS_SEL', s_idx))]])
				if active:
					res = parse_session_group_active_filtered(list_sessions()[s_idx], api_id, api_hash, g_idx, parse_user_id, parse_user_name, exclude_admins, last_seen_days, include_recently, progress=progress)
				else:
					res = parse_session_group_filtered(list_sessions()[s_idx], api_id, api_hash, g_idx, parse_user_id, parse_user_name, exclude_admins, last_seen_days, include_recently, progress=progress)
				await event.edit(f"Готово: {progress.get('processed',0)}/{progress.get('total',0)}", buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]])
				if isinstance(res, dict) and res.get('error') == 'invalid_index':
					await event.edit('Неверный индекс', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]]); return
			except Exception as exc:
				await event.edit(f'Ошибка: {exc}', buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]]); return
			# Summarize
			if active:
				text = (
					f"Групп: {res['groups_processed']}\n"
					f"Сообщений просмотрено: {res['messages_scanned']}\n"
					f"Уникальных отправителей: {res['unique_senders']}\n"
					f"Подходят фильтрам: {res['matched']}\n"
					f"user-id записано: {res['written_userids']}\n"
					f"username записано: {res['written_usernames']}\n"
					f"Исключено админов: {res['excluded_admins']}\n"
					f"Исключено по неактивности: {res['excluded_inactive']}\n"
					f"Ошибок: {res['errors']}\n"
				)
			else:
				text = (
					f"Групп: {res['groups_processed']}\n"
					f"Участников всего: {res['participants_total']}\n"
					f"Подходят фильтрам: {res['matched']}\n"
					f"user-id записано: {res['written_userids']}\n"
					f"username записано: {res['written_usernames']}\n"
					f"Исключено админов: {res['excluded_admins']}\n"
					f"Исключено по неактивности: {res['excluded_inactive']}\n"
					f"Ошибок: {res['errors']}\n"
				)
			await event.edit(text, buttons=[[Button.inline('Назад', cb('SESS_SEL', s_idx))]])
		elif key == 'INV':
			s_idx = int(parts[1])
			user_states[event.sender_id] = {'action': 'invite', 's_idx': s_idx}
			await event.edit('Введите канал (например, @mychannel) и опционально лимит: "@channel 20"', buttons=[[Button.inline('Отмена', cb('SESS_SEL', s_idx))]])
		elif key == 'OPT':
			options = getoptions()
			b = [
				[Button.inline(f'user-id: {options[2].strip()}', cb('TOG', 'id'))],
				[Button.inline(f'user-name: {options[3].strip()}', cb('TOG', 'name'))],
				[Button.inline('Назад', cb('MAIN'))],
			]
			await event.edit('Опции:', buttons=b)
		elif key == 'TOG':
			what = parts[1]
			if what == 'id':
				_, _opts = toggle_option(2)
			else:
				_, _opts = toggle_option(3)
			b = [
				[Button.inline(f'user-id: {_opts[2].strip()}', cb('TOG', 'id'))],
				[Button.inline(f'user-name: {_opts[3].strip()}', cb('TOG', 'name'))],
				[Button.inline('Назад', cb('MAIN'))],
			]
			await event.edit('Опции:', buttons=b)
		elif key == 'CLR':
			open('usernames.txt', 'w').close(); open('userids.txt', 'w').close()
			await event.edit('Очищено usernames.txt и userids.txt', buttons=[[Button.inline('Назад', cb('MAIN'))]])
		elif key == 'CFG':
			options = getoptions()
			text = (
				f"API_ID: {options[0].strip()}\nAPI_HASH: {options[1].strip()}\n"
				f"parse user-id: {options[2].strip()}\nparse user-name: {options[3].strip()}"
			)
			await event.edit(text, buttons=[[Button.inline('Назад', cb('MAIN'))]])
		else:
			await event.answer()

	@client.on(events.NewMessage)
	async def stateful_text_handler(event):
		# Handle text input after button prompts (e.g., invite channel)
		if not event.is_private:
			return
		if not is_allowed_user(event.sender_id):
			return
		st = user_states.get(event.sender_id)
		if not st:
			return
		if st.get('action') == 'invite':
			parts = event.raw_text.strip().split()
			if not parts:
				await event.respond('Формат: @channel [limit]')
				return
			channel = parts[0]
			if channel.startswith('@'):
				channel = channel[1:]
			try:
				limit = int(parts[1]) if len(parts) > 1 else 20
			except Exception:
				limit = 20
			s_idx = int(st['s_idx'])
			sessions = list_sessions()
			if s_idx < 0 or s_idx >= len(sessions):
				await event.respond('Неверная сессия')
				user_states.pop(event.sender_id, None)
				return
			try:
				progress = {'processed': 0, 'total': 0}
				await event.respond('Инвайт запущен... 0/0')
				summary = invite_from_usernames_with_summary(sessions[s_idx], api_id, api_hash, channel, limit, progress=progress)
			except Exception as exc:
				await event.respond(f'Ошибка инвайта: {exc}')
				user_states.pop(event.sender_id, None)
				return
			await event.respond(f"Инвайт прогресс: {progress.get('processed',0)}/{progress.get('total',0)}")
			text = (
				f"Канал: {summary['channel']}\n"
				f"Попыток: {summary['attempted']}\n"
				f"Инвайтов: {summary['invited']}\n"
				f"Уже участник: {summary['already_member']}\n"
				f"Приватность: {summary['skipped_privacy']}\n"
				f"Нет прав админа: {summary['admin_required']}\n"
				f"FloodWait: {summary['flood_wait']}\n"
				f"Ошибок: {summary['errors']} {('— ' + summary['last_error']) if summary['last_error'] else ''}"
			)
			await event.respond(text)
			user_states.pop(event.sender_id, None)
		elif st.get('action') == 'add_session':
			step = st.get('step', 'ask_name')
			text = event.raw_text.strip()
			if step == 'ask_name':
				# Validate session name and create client
				allowed = "._-"
				if not text or not all(ch.isalnum() or ch in allowed for ch in text.replace('.session','')):
					await event.respond('Имя должно содержать только буквы/цифры/._-')
					return
				if text.endswith('.session'):
					session_name = text[:-8]
					session_filename = text
				else:
					session_name = text
					session_filename = text + '.session'
				if os.path.exists(session_filename):
					await event.respond('Такое имя уже существует. Введите другое.'); return
				try:
					api_id2, api_hash2 = get_api_credentials()
					client2 = TelegramClient(session_name, api_id2, api_hash2)
					st.update({'client': client2, 'session_filename': session_filename, 'step': 'ask_phone'})
					user_states[event.sender_id] = st
					await event.respond('Введите номер телефона (в международном формате):')
				except Exception as exc:
					await event.respond(f'Ошибка инициализации: {exc}')
					user_states.pop(event.sender_id, None)
			elif step == 'ask_phone':
				st['phone'] = text
				user_states[event.sender_id] = st
				try:
					st['client'].connect()
					st['client'].send_code_request(text)
					st['step'] = 'ask_code'
					user_states[event.sender_id] = st
					await event.respond('Введите код из Telegram (например, 12345):')
				except Exception as exc:
					await event.respond(f'Ошибка отправки кода: {exc}')
					user_states.pop(event.sender_id, None)
			elif step == 'ask_code':
				code = text.replace(' ', '')
				try:
					st['client'].sign_in(phone=st['phone'], code=code)
					st['authorized'] = True
					try:
						st['client'].disconnect()
					except Exception:
						pass
					await event.respond('Сессия создана и авторизована. Готово ✅')
					user_states.pop(event.sender_id, None)
				except SessionPasswordNeededError:
					st['step'] = 'ask_2fa'
					user_states[event.sender_id] = st
					await event.respond('Включена двухфакторная аутентификация. Введите пароль:')
				except (PhoneCodeInvalidError, PhoneCodeExpiredError):
					await event.respond('Неверный или просроченный код. Повторите ввод кода:')
				except Exception as exc:
					await event.respond(f'Ошибка авторизации: {exc}')
					user_states.pop(event.sender_id, None)
			elif step == 'ask_2fa':
				password = text
				try:
					st['client'].sign_in(password=password)
					st['authorized'] = True
					try:
						st['client'].disconnect()
					except Exception:
						pass
					await event.respond('Сессия создана и авторизована. Готово ✅')
					user_states.pop(event.sender_id, None)
				except Exception as exc:
					await event.respond(f'Ошибка 2FA: {exc}')
					user_states.pop(event.sender_id, None)
		return

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

	@client.on(events.NewMessage(pattern=r'^/parse_active\s+(\d+)\s+(\d+|all)(?:\s+(\d+))?$'))
	async def parse_active_handler(event):
		if not is_allowed_user(event.sender_id):
			return
		parts = event.raw_text.split()
		if len(parts) < 3:
			await event.respond('Формат: /parse_active <s_idx> <g_idx|all> [limit]')
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
		limit = None
		if len(parts) >= 4:
			try:
				limit = int(parts[3])
			except Exception:
				limit = None
		options = getoptions()
		parse_user_id = options[2] == 'True\n'
		parse_user_name = options[3] == 'True\n'
		try:
			result = parse_session_group_active(
				sessions[s_idx], api_id, api_hash, group_index, parse_user_id, parse_user_name, limit
			)
		except Exception as exc:
			await event.respond(f'Ошибка парсинга: {exc}')
			return
		await event.respond(f'Готово: {result}')

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

	@client.on(events.NewMessage(pattern=r'^/add_session$'))
	async def add_session_cmd(event):
		if not is_allowed_user(event.sender_id):
			return
		user_states[event.sender_id] = {'action': 'add_session', 'step': 'ask_name', 'authorized': False}
		await event.respond('Введите имя сессии (латиница/цифры . _ -). Можно без .session')

	print('[bot] Бот запущен. Ожидаю команды...')
	client.run_until_disconnected()


if __name__ == '__main__':
	main()

