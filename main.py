import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

# Настройки бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Настройки для yt-dlp
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
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Очередь воспроизведения
queues = {}

@bot.event
async def on_ready():
    print(f'Бот {bot.user} готов к работе!')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!play"))

@bot.command()
async def play(ctx, *, query):
    """Воспроизводит музыку с YouTube"""
    if not ctx.author.voice:
        await ctx.send("Вы должны быть в голосовом канале!")
        return
    
    voice_channel = ctx.author.voice.channel
    
    if ctx.voice_client is None:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)
    
    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
            
            # Добавляем в очередь
            if ctx.guild.id not in queues:
                queues[ctx.guild.id] = []
            
            queues[ctx.guild.id].append(player)
            
            # Если ничего не играет, начинаем воспроизведение
            if not ctx.voice_client.is_playing():
                await play_next(ctx)
            else:
                await ctx.send(f'🎵 Добавлено в очередь: **{player.title}**')
                
        except Exception as e:
            await ctx.send(f'❌ Произошла ошибка: {str(e)}')

@bot.command()
async def skip(ctx):
    """Пропускает текущий трек"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send('⏭️ Трек пропущен!')
    else:
        await ctx.send('❌ Сейчас ничего не играет!')

async def play_next(ctx):
    """Воспроизводит следующий трек из очереди"""
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        player = queues[ctx.guild.id].pop(0)
        ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
        await ctx.send(f'🎵 Сейчас играет: **{player.title}**')
    else:
        await ctx.send('🎵 Очередь пуста!')

@bot.command()
async def stop(ctx):
    """Останавливает музыку и очищает очередь"""
    if ctx.voice_client:
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
        ctx.voice_client.stop()
        await ctx.send('⏹️ Музыка остановлена!')

@bot.command()
async def leave(ctx):
    """Покидает голосовой канал"""
    if ctx.voice_client:
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
        await ctx.voice_client.disconnect()
        await ctx.send('👋 Покидаю голосовой канал!')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"Error: {error}")

# Запуск бота
if __name__ == "__main__":
    token = os.getenv('BOT_TOKEN')
    if not token:
        print("Ошибка: BOT_TOKEN не найден в переменных окружения")
    else:
        bot.run(token)
