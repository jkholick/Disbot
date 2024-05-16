import asyncio
from os.path import isfile
import pickle

from  decouple import config
import discord
import yt_dlp

from discord.ext import commands

# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''

servers={}
if isfile("./servers.pickle"):
    with open('servers.pickle', 'rb') as openfile:
        servers = pickle.load(openfile)

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
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')
        self.artist = data.get('artist')
        
    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel (you gotta add the channel id)"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.command()
    async def play(self, ctx, *, url):
        """Streams from a url or search terms"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=False)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {player.title} - {player.artist}')

    @commands.command()
    async def volume(self,ctx,volume: int = None):
        """Set volume level or show volume level"""
        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")
        
        if volume is None:
            volume = ctx.voice_client.source.volume*100
            return await ctx.send(f"Volume level is {volume}%")
        
        if 0 <= volume <= 100:
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"Changed volume to {volume}%")
        else:
            await ctx.send("Volume must be between 0 and 100")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""

        await ctx.voice_client.disconnect()

    @play.before_invoke
    async def ensure_voice(self, ctx):
        await self.check_music_channel(ctx)
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()


    @join.before_invoke
    @stop.before_invoke
    @volume.before_invoke
    async def check_music_channel(self,ctx):
        global servers
        
        if ctx.guild.id in servers:
            if servers[ctx.guild.id]["music_channel"] != ctx.channel.id:
                raise commands.CommandError("Message not in music channel")

    def is_guild_owner():
        def predicate(ctx):
            return ctx.guild is not None and ctx.guild.owner_id == ctx.author.id
        return commands.check(predicate)
    
    @commands.command()
    @commands.check_any(commands.is_owner(), is_guild_owner())
    async def set_music_channel(self,ctx,channel = "None"):
        """Set a specific channel for music commands(server owner only)
            Usage: set_music_channel #channel_name (channel name optional)
        """

        global servers
        
        if channel == "None":
            if ctx.guild in servers:
                servers[ctx.guild.id]["music_channel_bot"] = ctx.channel.id
            else:
                servers[ctx.guild.id] = {"music_channel": ctx.channel.id}
            
            await ctx.send("Setting current channel <#"+ str(ctx.channel.id) +"> as music channel")
        else:
            if ctx.guild in servers:
                servers[ctx.guild.id]["music_channel_bot"] = int(channel[2:-1])
            else:
                servers[ctx.guild.id] = {"music_channel": int(channel[2:-1])}
            
            await ctx.send("Set "+ channel +" as music channel")
        
        with open("servers.pickle", "wb") as outfile:
            pickle.dump(servers, outfile)
            

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(""),
    description='A potato Bot make my a lifeless person (jkholick)',
    intents=intents,
)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(config("BOT_TOKEN"))


asyncio.run(main())
