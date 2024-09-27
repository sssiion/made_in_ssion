from dico_totalbot_token import Token
import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
from pytz import timezone
import asyncio
from tqdm import tqdm  # 진행 상황 표시용 라이브러리

# intents 설정
intents = discord.Intents.default()
intents.message_content = True        # 메시지 내용 접근
intents.guilds = True                 # 서버 관련 이벤트 접근
intents.members = True                # 서버 멤버 정보 접근 (필요 시)

bot = commands.Bot(command_prefix='!', intents=intents)

# 데이터 저장 파일
DATA_FILE = 'user_data.json'

# 데이터 로드 함수
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}  # 파일이 없으면 빈 딕셔너리 반환
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}  # 파일이 손상된 경우 빈 딕셔너리 반환

# 데이터 저장 함수
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return  # 봇의 메시지는 무시

    data = load_data()
    user_id = str(message.author.id)
    current_date = datetime.now(timezone('Asia/Seoul')).strftime('%Y-%m-%d')

    if user_id not in data:
        data[user_id] = {'name': str(message.author), 'messages': {}}

    data[user_id]['messages'][current_date] = data[user_id]['messages'].get(current_date, 0) + 1

    save_data(data)
    await bot.process_commands(message)  # 명령어 처리를 계속 진행

@bot.command(name='통계')
async def stats(ctx, member: discord.Member = None, date: str = None):
    """
    특정 사용자의 특정 날짜 메시지 수를 조회합니다.
    사용법: !통계 [@사용자] [YYYY-MM-DD]
    """
    data = load_data()
    member = member or ctx.author
    user_id = str(member.id)

    if user_id in data and 'messages' in data[user_id]:
        if date:
            try:
                # 날짜 형식 검증
                datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
            except ValueError:
                await ctx.send("날짜 형식이 올바르지 않습니다. `YYYY-MM-DD` 형식으로 입력해주세요.")
                return

            count = data[user_id]['messages'].get(date, 0)
            await ctx.send(f'{member.display_name}님의 {date} 메시지 수: {count}개')
        else:
            # 전체 메시지 수 계산
            total = sum(data[user_id]['messages'].values())
            await ctx.send(f'{member.display_name}님의 전체 메시지 수: {total}개')
    else:
        await ctx.send(f'{member.display_name}님의 메시지 기록이 없습니다.')

@bot.command(name='기간통계')
async def period_stats(ctx, member: discord.Member = None, start_date: str = None, end_date: str = None):
    """
    특정 사용자의 특정 기간 동안 메시지 수를 조회합니다.
    사용법: !기간통계 [@사용자] [YYYY-MM-DD] [YYYY-MM-DD]
    """
    data = load_data()
    member = member or ctx.author
    user_id = str(member.id)

    if not start_date or not end_date:
        await ctx.send("시작일과 종료일을 모두 입력해주세요. `YYYY-MM-DD` 형식으로 입력해주세요.")
        return

    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
        end = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
        if start > end:
            await ctx.send("시작일이 종료일보다 이후일 수 없습니다.")
            return
    except ValueError:
        await ctx.send("날짜 형식이 올바르지 않습니다. `YYYY-MM-DD` 형식으로 입력해주세요.")
        return

    if user_id in data and 'messages' in data[user_id]:
        total = 0
        for date_str, count in data[user_id]['messages'].items():
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
                if start <= date_obj <= end:
                    total += count
            except ValueError:
                continue  # 잘못된 날짜 형식은 무시
        await ctx.send(f'{member.display_name}님의 {start_date}부터 {end_date}까지 메시지 수: {total}개')
    else:
        await ctx.send(f'{member.display_name}님의 메시지 기록이 없습니다.')

@bot.command(name='수집기간', help='특정 기간 동안의 메시지를 수집합니다. 관리자만 사용 가능합니다.')
@commands.has_permissions(administrator=True)
async def collect_history_period(ctx, start_date: str, end_date: str, limit: int = 100):
    """
    특정 기간 동안 이루어진 대화의 메시지를 수집합니다.
    사용법: !수집기간 [YYYY-MM-DD] [YYYY-MM-DD] [메시지 수 제한]
    기본값: 100
    """
    await ctx.send(f"{start_date}부터 {end_date}까지의 메시지 수집을 시작합니다. 잠시만 기다려 주세요...")
    data = load_data()
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
        end = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
        if start > end:
            await ctx.send("시작일이 종료일보다 이후일 수 없습니다.")
            return
    except ValueError:
        await ctx.send("날짜 형식이 올바르지 않습니다. `YYYY-MM-DD` 형식으로 입력해주세요.")
        return

    try:
        for channel in ctx.guild.text_channels:
            if not channel.permissions_for(ctx.guild.me).read_message_history:
                await ctx.send(f"{channel.name} 채널의 메시지 기록을 읽을 수 없습니다.")
                continue

            messages = []
            async for message in channel.history(limit=limit, oldest_first=True):
                if start <= message.created_at <= end:
                    messages.append(message)

            for message in tqdm(messages, desc=f"Collecting messages from {channel.name}"):
                if message.author.bot:
                    continue  # 봇의 메시지는 무시

                user_id = str(message.author.id)
                current_date = message.created_at.astimezone(timezone('Asia/Seoul')).strftime('%Y-%m-%d')  # 메시지 생성 날짜

                if user_id in data:
                    if 'messages' in data[user_id]:
                        if current_date in data[user_id]['messages']:
                            data[user_id]['messages'][current_date] += 1
                        else:
                            data[user_id]['messages'][current_date] = 1
                    else:
                        data[user_id]['messages'] = {current_date: 1}
                else:
                    data[user_id] = {
                        'name': str(message.author),
                        'messages': {
                            current_date: 1
                        }
                    }

            save_data(data)

        await ctx.send("특정 기간 메시지 수집이 완료되었습니다.")
    except Exception as e:
        await ctx.send(f"메시지 수집 중 오류가 발생했습니다: {e}")


@bot.command(name='전체통계')
@commands.has_permissions(administrator=True)
async def global_stats(ctx, date: str = None, start_date: str = None, end_date: str = None):
    """
    전체 서버의 메시지 통계를 조회합니다.
    사용법:
        !전체통계 [YYYY-MM-DD]
        !전체통계 [YYYY-MM-DD] [YYYY-MM-DD]
    """
    data = load_data()
    message = "전체 메시지 통계:\n"

    if date:
        # 단일 날짜 통계
        try:
            datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
        except ValueError:
            await ctx.send("날짜 형식이 올바르지 않습니다. `YYYY-MM-DD` 형식으로 입력해주세요.")
            return

        for user in data.values():
            count = user.get('messages', {}).get(date, 0)
            if count > 0:
                message += f"{user['name']}: {count}개\n"

    elif start_date and end_date:
        # 기간 통계
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
            if start > end:
                await ctx.send("시작일이 종료일보다 이후일 수 없습니다.")
                return
        except ValueError:
            await ctx.send("날짜 형식이 올바르지 않습니다. `YYYY-MM-DD` 형식으로 입력해주세요.")
            return

        for user in data.values():
            total = 0
            for date_str, count in user.get('messages', {}).items():
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone('Asia/Seoul'))
                    if start <= date_obj <= end:
                        total += count
                except ValueError:
                    continue  # 잘못된 날짜 형식은 무시
            if total > 0:
                message += f"{user['name']}: {total}개\n"
    else:
        # 전체 기간 통계
        sorted_data = []
        for user in data.values():
            total = sum(user.get('messages', {}).values())
            sorted_data.append({'name': user['name'], 'count': total})
        sorted_data = sorted(sorted_data, key=lambda x: x['count'], reverse=True)
        for user in sorted_data:
            message += f"{user['name']}: {user['count']}개\n"

    if message == "전체 메시지 통계:\n":
        message += "데이터가 없습니다."

    await ctx.send(message)

@bot.command(name='수집', help='봇이 실행되기 전에 이루어진 대화(예: 2022년)의 메시지를 수집합니다. 관리자만 사용 가능합니다.')
@commands.has_permissions(administrator=True)
async def collect_history(ctx, limit: int = 100):
    """
    봇이 실행되기 전에 이루어진 대화의 메시지를 수집합니다.
    사용법: !수집 [메시지 수 제한]
    기본값: 100
    """
    await ctx.send("메시지 수집을 시작합니다. 잠시만 기다려 주세요...")
    data = load_data()
    try:
        for channel in ctx.guild.text_channels:
            if not channel.permissions_for(ctx.guild.me).read_message_history:
                await ctx.send(f"{channel.name} 채널의 메시지 기록을 읽을 수 없습니다.")
                continue

            messages = []
            async for message in channel.history(limit=limit, oldest_first=True):
                messages.append(message)

            for message in tqdm(messages, desc=f"Collecting messages from {channel.name}"):
                if message.author.bot:
                    continue  # 봇의 메시지는 무시

                user_id = str(message.author.id)
                current_date = message.created_at.astimezone(timezone('Asia/Seoul')).strftime('%Y-%m-%d')  # 메시지 생성 날짜

                if user_id in data:
                    if 'messages' in data[user_id]:
                        if current_date in data[user_id]['messages']:
                            data[user_id]['messages'][current_date] += 1
                        else:
                            data[user_id]['messages'][current_date] = 1
                    else:
                        data[user_id]['messages'] = {current_date: 1}
                else:
                    data[user_id] = {
                        'name': str(message.author),
                        'messages': {
                            current_date: 1
                        }
                    }

            save_data(data)

        await ctx.send("메시지 수집이 완료되었습니다.")
    except Exception as e:
        await ctx.send(f"메시지 수집 중 오류가 발생했습니다: {e}")

# 봇 실행
bot.run(Token)
