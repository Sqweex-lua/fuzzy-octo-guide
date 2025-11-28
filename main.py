import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

# Настройки бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Очереди для серверов
queues = {}
current = {}

# Настройки yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class MusicSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            
            if 'entries' in data:
                if data['entries']:
                    data = data['entries'][0]
                else:
                    raise Exception("Не найдено треков")
            
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except Exception as e:
            raise Exception(f"Ошибка загрузки: {str(e)}")

def check_queue(ctx, guild_id):
    if queues.get(guild_id):
        if queues[guild_id]:
            source = queues[guild_id].pop(0)
            current[guild_id] = source
            ctx.voice_client.play(source, after=lambda x=None: check_queue(ctx, guild_id))

@bot.event
async def on_ready():
    print(f'🎵 Бот {bot.user} готов к работе!')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/play"))

@bot.command()
async def play(ctx, *, query):
    """Воспроизвести музыку"""
    try:
        if not ctx.author.voice:
            await ctx.send("❌ Сначала зайдите в голосовой канал!")
            return

        voice_channel = ctx.author.voice.channel
        
        if ctx.voice_client is None:
            await voice_channel.connect()
        elif ctx.voice_client.channel != voice_channel:
            await ctx.voice_client.move_to(voice_channel)

        async with ctx.typing():
            if "soundcloud.com" in query.lower() or "on.soundcloud.com" in query.lower():
                player = await MusicSource.from_url(query, stream=True)
            else:
                player = await MusicSource.from_url(f"ytsearch:{query}", stream=True)
            
            guild_id = ctx.guild.id
            
            if not ctx.voice_client.is_playing():
                current[guild_id] = player
                ctx.voice_client.play(player, after=lambda x=None: check_queue(ctx, guild_id))
                await ctx.send(f"🎵 Сейчас играет: **{player.title}**")
            else:
                if guild_id not in queues:
                    queues[guild_id] = []
                queues[guild_id].append(player)
                await ctx.send(f"✅ Добавлено в очередь: **{player.title}**")
                
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {str(e)}")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Трек пропущен")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        guild_id = ctx.guild.id
        if guild_id in queues:
            queues[guild_id].clear()
        ctx.voice_client.stop()
        await ctx.send("⏹️ Музыка остановлена")

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Пауза")

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Продолжаем")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Покидаю канал")

@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and queues[guild_id]:
        queue_list = "\n".join([f"{i+1}. {track.title}" for i, track in enumerate(queues[guild_id][:10])])
        await ctx.send(f"**Очередь:**\n{queue_list}")
    else:
        await ctx.send("📭 Очередь пуста")

# Запуск бота
bot.run(os.environ['BOT_TOKEN'])
