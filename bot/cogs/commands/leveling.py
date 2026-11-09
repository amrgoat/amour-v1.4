import discord 
from utils.emoji import CROSS, TICK, ZWARNING
from utils.Tools import getConfig
from utils.cv2_store import build_view, get_template
from utils.embed_store import get_embed, render_embed
from utils.variables import build_variables, find_template_tokens, render
from utils.varhelp import VariablesView
from discord import app_commands 
from discord .ext import commands 
from discord.ext import tasks
import aiosqlite 
import asyncio 
import json 
import re 
import random 
import math 
from datetime import datetime ,timezone ,timedelta 

IST = timezone(timedelta(hours=5, minutes=30), name="IST")
from typing import Optional ,Dict ,List ,Tuple 
try :
    from PIL import Image ,ImageDraw ,ImageFont ,ImageFilter ,ImageEnhance 
    PIL_AVAILABLE =True 
except ImportError :
    PIL_AVAILABLE =False 
import io 
import os 
import requests 
import logging 


logger =logging .getLogger ('discord')


def utc_to_local (dt :datetime )->datetime :
    return dt .replace (tzinfo =timezone .utc )

def format_number (num :int )->str :
    """Format numbers with commas for better readability"""
    return f"{num:,}"

def calculate_level_from_xp (xp :int )->int :
    """Calculate level from XP using standard formula"""
    if xp <0 :
        return 0 
    return int (math .sqrt (xp /100 ))

def calculate_xp_for_level (level :int )->int :
    """Calculate XP required for a specific level"""
    return level *level *100 

def get_level_progress (xp :int )->tuple :
    """Get current level, XP for current level, and XP for next level"""
    current_level =calculate_level_from_xp (xp )
    current_level_xp =calculate_xp_for_level (current_level )
    next_level_xp =calculate_xp_for_level (current_level +1 )
    progress =xp -current_level_xp 
    needed =next_level_xp -current_level_xp 
    return current_level ,progress ,needed 

def get_progress_bar (current :int ,total :int ,length :int =10 )->str :
    """Create a visual progress bar"""
    if total ==0 :
        return "▱"*length 
    filled =int ((current /total )*length )
    return "▰"*filled +"▱"*(length -filled )

def validate_hex_color (color :str )->bool :
    """Validate hex color format"""
    if not color .startswith ('#'):
        return False 
    return bool (re .match (r'^#(?:[0-9a-fA-F]{3}){1,2}$',color ))

def hex_to_int (hex_color :str )->int :
    """Convert hex color to integer"""
    try :
        if not hex_color .startswith ('#'):
            hex_color ='#'+hex_color 
        return int (hex_color .lstrip ('#'),16 )
    except (ValueError ,TypeError ):
        return 0xFF0000 

class LevelConfigModal (discord .ui .Modal ,title ="Leveling System Configuration"):
    def __init__ (self ,cog ,current_settings ):
        super ().__init__ ()

        self .cog =cog 


        current_low =current_settings .get ('min_xp')or current_settings .get ('xp_per_message',20 )
        current_high =current_settings .get ('max_xp')or current_low 
        if current_low ==current_high :
            current_range =str (current_low )
        else :
            current_range =f"{current_low}-{current_high}"

        self .xp_per_message =discord .ui .TextInput (
        label ="Chat XP per Message (number or range)",
        placeholder ="15-25 or 20",
        default =current_range ,
        required =True ,
        max_length =7 
        )

        self .level_up_message =discord .ui .TextInput (
        label ="Level Up Message (plain text)",
        placeholder ="{user} · {level} · {earned:(role)} · {embed:name} · {cv2:name}",
        default =current_settings .get ('level_message','Congratulations {user}! You have reached level {level}!'),
        required =True ,
        style =discord .TextStyle .paragraph ,
        max_length =2000 
        )


        self .add_item (self .xp_per_message )
        self .add_item (self .level_up_message )

    async def on_submit (self ,interaction :discord .Interaction ):
        try :
            if not interaction or not hasattr (interaction ,'response'):
                logger .error ("Invalid interaction object in LevelConfigModal")
                return 

            await interaction .response .defer (ephemeral =True )


            parsed_range =parse_xp_range (self .xp_per_message .value )
            if parsed_range is None :
                await interaction .followup .send (
                f"{CROSS} Invalid XP value! Use a number like `20` or a range like `15-25` (each 1-999).",
                ephemeral =True )
                return 
            xp_low ,xp_high =parsed_range 
            xp_value =xp_high 

            try :
                async with aiosqlite .connect ("db/leveling.db")as db :

                    async with db .execute ("SELECT guild_id FROM leveling_settings WHERE guild_id = ?",(interaction .guild .id ,))as cursor :
                        exists =await cursor .fetchone ()

                    if exists :

                        await db .execute ("""
                            UPDATE leveling_settings 
                            SET enabled = ?, xp_per_message = ?, level_message = ?, min_xp = ?, max_xp = ?
                            WHERE guild_id = ?
                        """,(
                        1 ,
                        xp_value ,
                        self .level_up_message .value ,
                        xp_low ,
                        xp_high ,
                        interaction .guild .id 
                        ))
                        logger .info (f"Updated settings for guild {interaction.guild.id}")
                    else :

                        await db .execute ("""
                            INSERT INTO leveling_settings 
                            (guild_id, enabled, xp_per_message, level_message, min_xp, max_xp,
                             cooldown_seconds, dm_level_up, channel_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,(
                        interaction .guild .id ,
                        1 ,
                        xp_value ,
                        self .level_up_message .value ,
                        xp_low ,
                        xp_high ,
                        60 ,
                        0 ,
                        None 
                        ))
                        logger .info (f"Created new settings for guild {interaction.guild.id}")

                    await db .commit ()
                    logger .info (f"Settings saved successfully for guild {interaction.guild.id}")

            except Exception as e :
                return 


            embed =discord .Embed (
            title =f"{TICK} Leveling Configuration Updated",
            description =f"**XP per Message:** {xp_low}-{xp_high}\n"
            f"**Level Up Message:** {self.level_up_message.value[:50]}{'...' if len(self.level_up_message.value) > 50 else ''}",
            color =0xFF0000 ,
            timestamp =datetime .now (IST )
            )


            view =VariablesView (interaction .user )
            await interaction .followup .send (embed =embed ,view =view ,ephemeral =True )

        except Exception as e :
            logger .error (f"Critical error in LevelConfigModal: {e}")
            await interaction .followup .send (
            f"{CROSS} An unexpected error occurred: {str(e)}",
            ephemeral =True 
            )

DEFAULT_VC_MESSAGE = "🎧 {user} reached voice level {level}!"


def parse_xp_range (raw ):
    """Parse ``20`` or ``15-25`` into ``(low, high)``."""
    if raw is None :
        return None 
    text =str (raw ).strip ().replace (" ","").replace ("–","-")
    match =re .fullmatch (r"(\d{1,3})(?:-(\d{1,3}))?",text )
    if not match :
        return None 
    low =int (match .group (1 ))
    high =int (match .group (2 ))if match .group (2 )else low 
    if low >high :
        low ,high =high ,low 
    if low <1 or high >999 :
        return None 
    return low ,high 


def _preview (text ,limit =80 ):
    text =text or ""
    return text if len (text )<=limit else text [:limit -3 ]+"..."


def _leveling_summary (settings ):
    low =settings .get ('min_xp')or settings .get ('xp_per_message')or 20 
    high =settings .get ('max_xp')or low 
    xp_text =str (low )if low ==high else f"{low}-{high}"
    channel_id =settings .get ('channel_id')
    channel_text =f"<#{channel_id}>"if channel_id else "Same channel as the message"
    return (
    f"Status: **{'Enabled' if settings.get('enabled') else 'Disabled'}**\n"
    f"Chat XP per message: `{xp_text}`\n"
    f"Cooldown: `{settings.get('cooldown_seconds', 60)}s`\n"
    f"Level-up channel: {channel_text}\n"
    f"Level-up message: `{_preview(settings.get('level_message'))}`"
    )


def _vc_summary (settings ):
    low =settings .get ('min_xp',10 )
    high =settings .get ('max_xp',20 )
    xp_text =str (low )if low ==high else f"{low}-{high}"
    channel_id =settings .get ('channel_id')
    channel_text =f"<#{channel_id}>"if channel_id else "The voice channel they are in"
    return (
    f"Status: **{'Enabled' if settings.get('enabled') else 'Disabled'}**\n"
    f"Voice XP per minute: `{xp_text}`\n"
    f"Level-up channel: {channel_text}\n"
    f"Level-up message: `{_preview(settings.get('level_message') or DEFAULT_VC_MESSAGE)}`"
    )


class SettingsLauncherView (discord .ui .View ):
    """A button that opens a settings modal.

    Prefix commands cannot answer with a modal directly, so they post this
    launcher instead of asking the admin questions one message at a time.
    """

    def __init__ (self ,build_modal ,label ="Open Settings",emoji ="⚙️"):
        super ().__init__ (timeout =180 )
        self ._build_modal =build_modal 
        button =discord .ui .Button (label =label ,style =discord .ButtonStyle .primary ,emoji =emoji )
        button .callback =self ._open 
        self .add_item (button )

    async def _open (self ,interaction :discord .Interaction ):
        await interaction .response .send_modal (self ._build_modal ())


class VCConfigModal (discord .ui .Modal ,title ="VC Leveling Configuration"):
    def __init__ (self ,cog ,current_settings ):
        super ().__init__ ()
        self .cog =cog 

        low =current_settings .get ('min_xp',10 )
        high =current_settings .get ('max_xp',20 )
        xp_default =str (low )if low ==high else f"{low}-{high}"

        self .xp_range =discord .ui .TextInput (
        label ="Voice XP per minute (number or range)",
        placeholder ="10-20 or 15",
        default =xp_default ,
        required =True ,
        max_length =7 
        )

        self .level_up_message =discord .ui .TextInput (
        label ="VC Level Up Message (plain text)",
        placeholder ="{user} reached voice level {level}! · {embed:name} · {cv2:name}",
        default =current_settings .get ('level_message')or DEFAULT_VC_MESSAGE ,
        required =True ,
        style =discord .TextStyle .paragraph ,
        max_length =2000 
        )

        self .add_item (self .xp_range )
        self .add_item (self .level_up_message )

    async def on_submit (self ,interaction :discord .Interaction ):
        parsed =parse_xp_range (self .xp_range .value )
        if parsed is None :
            await interaction .response .send_message (
            f"{CROSS} Invalid XP value! Use `15` or a range like `10-20` (each 1-999).",
            ephemeral =True )
            return 

        low ,high =parsed 
        await self .cog .save_vc_settings (
        interaction .guild .id ,
        min_xp =low ,
        max_xp =high ,
        level_message =self .level_up_message .value 
        )

        xp_text =str (low )if low ==high else f"{low}-{high}"
        embed =discord .Embed (
        title =f"{TICK} VC Leveling Updated",
        description =f"**Voice XP per minute:** `{xp_text}`\n"
        f"**VC level-up message:** `{_preview(self.level_up_message.value)}`",
        color =0x00FF00 ,
        timestamp =datetime .now (IST )
        )
        await interaction .response .send_message (
        embed =embed ,view =VariablesView (interaction .user ),ephemeral =True )


DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class LeaderboardScheduleModal (discord .ui .Modal ,title ="Leaderboard Schedule (IST)"):
    def __init__ (self ,cog ,guild ,channel =None ,period =None ,day =None ,time =None ):
        super ().__init__ ()
        self .cog =cog 
        self .guild =guild 

        self .channel =discord .ui .TextInput (
        label ="Channel (#name or ID)",
        placeholder ="#leaderboard",
        default =channel ,
        required =True ,
        max_length =100 
        )
        self .period =discord .ui .TextInput (
        label ="Period (daily or weekly)",
        placeholder ="daily",
        default =period or "daily",
        required =True ,
        max_length =10 
        )
        self .day =discord .ui .TextInput (
        label ="Day (weekly only)",
        placeholder ="monday",
        default =day ,
        required =False ,
        max_length =10 
        )
        self .time =discord .ui .TextInput (
        label ="Time in IST (24h HH:MM)",
        placeholder ="20:30",
        default =time ,
        required =True ,
        max_length =5 
        )

        for item in (self .channel ,self .period ,self .day ,self .time ):
            self .add_item (item )

    async def on_submit (self ,interaction :discord .Interaction ):
        await interaction .response .defer (ephemeral =True )

        channel =self .cog ._find_text_channel (self .guild ,self .channel .value )
        if channel is None :
            await interaction .followup .send (f"{CROSS} I couldn't find that channel.",ephemeral =True )
            return 

        period =(self .period .value or "").strip ().lower ()
        if period not in ("daily","weekly"):
            await interaction .followup .send (f"{CROSS} Period must be `daily` or `weekly`.",ephemeral =True )
            return 

        weekday =None 
        if period =="weekly":
            weekday =self .cog ._parse_weekday (self .day .value )
            if weekday is None :
                await interaction .followup .send (
                f"{CROSS} For a weekly schedule the day must be monday to sunday.",ephemeral =True )
                return 

        time_ist =self .cog ._parse_hhmm (self .time .value )
        if time_ist is None :
            await interaction .followup .send (
            f"{CROSS} That time isn't valid — use 24-hour `HH:MM`, e.g. `20:30`.",ephemeral =True )
            return 

        await self .cog .save_leaderboard_schedule (self .guild .id ,channel .id ,period ,weekday ,time_ist )

        embed =discord .Embed (
        title =f"{TICK} Leaderboard Schedule Saved",
        description =self .cog ._schedule_confirmation (channel ,period ,weekday ,time_ist ),
        color =0x00FF00 ,
        timestamp =datetime .now (IST )
        )
        await interaction .followup .send (embed =embed ,ephemeral =True )


class LeaderboardLiveModal (discord .ui .Modal ,title ="Live Leaderboard"):
    def __init__ (self ,cog ,guild ,fallback_channel ,interval =30 ):
        super ().__init__ ()
        self .cog =cog 
        self .guild =guild 
        self .fallback_channel =fallback_channel 
        self .channel =discord .ui .TextInput (
        label ="Channel (#name or ID, blank = this one)",
        placeholder ="#leaderboard",
        required =False ,
        max_length =100 
        )
        self .interval =discord .ui .TextInput (
        label ="Refresh interval in minutes (1-1440)",
        placeholder ="30",
        default =str (interval ),
        required =True ,
        max_length =4 
        )
        self .add_item (self .channel )
        self .add_item (self .interval )

    async def on_submit (self ,interaction :discord .Interaction ):
        await interaction .response .defer (ephemeral =True )

        raw =(self .channel .value or "").strip ()
        channel =self .cog ._find_text_channel (self .guild ,raw )if raw else self .fallback_channel 
        if channel is None :
            await interaction .followup .send (f"{CROSS} I couldn't find that channel.",ephemeral =True )
            return 

        try :
            minutes =int ((self .interval .value or "30").strip ())
        except ValueError :
            minutes =0 
        if minutes <1 or minutes >1440 :
            await interaction .followup .send (
            f"{CROSS} The interval must be a whole number of minutes between 1 and 1440.",ephemeral =True )
            return 

        interval =self .cog ._clamp_interval (minutes )
        await self .cog .start_live_leaderboard (self .guild ,channel ,interval )
        plural ="" if interval ==1 else "s"
        await interaction .followup .send (
        f"✅ Live leaderboard started in {channel.mention} — it refreshes every {interval} minute{plural} (chat + VC).",
        ephemeral =True )


def _clamp(value, limit=1024):
    value = value or ""
    return value if len(value) <= limit else value[:limit - 3] + "..."


def _reward_lines(guild, rows):
    lines = []
    for level, role_id, remove_previous in rows:
        role = guild.get_role(role_id)
        name = role.mention if role else f"role {role_id}"
        suffix = " (replaces previous)" if remove_previous else ""
        lines.append(f"\u2022 **Level {level}** \u2192 {name}{suffix}")
    return _clamp("\n".join(lines))


def _level_role_lines(guild, rows):
    lines = []
    for level, role_id in rows:
        role = guild.get_role(role_id)
        name = role.mention if role else f"role {role_id}"
        lines.append(f"\u2022 **Level {level}** \u2192 {name}")
    return _clamp("\n".join(lines))


def _multiplier_lines(guild, rows):
    lines = []
    for target_id, target_type, multiplier in rows:
        obj = guild.get_role(target_id) if target_type == "role" else guild.get_channel(target_id)
        name = obj.mention if obj else f"{target_type} {target_id}"
        lines.append(f"\u2022 {target_type.capitalize()}: {name} \u2192 **{multiplier}x**")
    return _clamp("\n".join(lines))


class Leveling (commands .Cog ):
    def __init__ (self ,bot ):
        self .bot =bot 
        self .message_cooldowns ={}
        self .last_level_cache ={}
        self .db_path ="db/leveling.db"

    @commands.group (name ="chatlevel",invoke_without_command =True ,description ="Chat leveling system")
    async def level (self ,ctx ):
        """Main leveling command"""
        if ctx .invoked_subcommand is None :
            await ctx .send_help (ctx .command )

    async def cog_load (self ):
        """Initialize database tables and start the background loops."""
        try :
            await self .init_database ()
            for loop in (self .vc_loop ,self .schedule_loop ,self .live_loop ):
                if not loop .is_running ():
                    loop .start ()
        except Exception as e :
            logger .error (f"Error loading Leveling cog: {e}")

    async def cog_unload (self ):
        for loop in (self .vc_loop ,self .schedule_loop ,self .live_loop ):
            if loop .is_running ():
                loop .cancel ()

    async def init_database (self ):
        """Initialize all required database tables"""
        try :
            async with aiosqlite .connect ("db/leveling.db")as db :

                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS user_xp (
                        guild_id INTEGER,
                        user_id INTEGER,
                        xp INTEGER DEFAULT 0,
                        messages INTEGER DEFAULT 0,
                        last_message_time TEXT,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)


                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS leveling_settings (
                        guild_id INTEGER PRIMARY KEY,
                        enabled INTEGER DEFAULT 0,
                        channel_id INTEGER,
                        level_message TEXT DEFAULT 'Congratulations {user}! You have reached level {level}!',
                        embed_color INTEGER DEFAULT 0,
                        level_image TEXT,
                        thumbnail_enabled INTEGER DEFAULT 1,
                        xp_per_message INTEGER DEFAULT 20,
                        min_xp INTEGER DEFAULT 15,
                        max_xp INTEGER DEFAULT 25,
                        cooldown_seconds INTEGER DEFAULT 60,
                        dm_level_up INTEGER DEFAULT 0
                    )
                """)


                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS level_rewards (
                        guild_id INTEGER,
                        level INTEGER,
                        role_id INTEGER,
                        remove_previous INTEGER DEFAULT 0,
                        PRIMARY KEY (guild_id, level)
                    )
                """)


                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS xp_multipliers (
                        guild_id INTEGER,
                        target_id INTEGER,
                        target_type TEXT,
                        multiplier REAL,
                        PRIMARY KEY (guild_id, target_id, target_type)
                    )
                """)


                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS leveling_blacklist (
                        guild_id INTEGER,
                        target_id INTEGER,
                        target_type TEXT,
                        PRIMARY KEY (guild_id, target_id, target_type)
                    )
                """)


                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS users (
                        guild_id INTEGER,
                        user_id INTEGER,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)

                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS level_roles (
                        guild_id INTEGER,
                        level INTEGER,
                        role_id INTEGER,
                        PRIMARY KEY (guild_id, level)
                    )
                """)


                async with db .cursor ()as cursor :

                    await cursor .execute ("PRAGMA table_info(leveling_blacklist)")
                    columns =[col [1 ]for col in await cursor .fetchall ()]
                    if "target_type"not in columns :
                        await cursor .execute ("ALTER TABLE leveling_blacklist ADD COLUMN target_type TEXT")
                        logger .info ("Added target_type column to leveling_blacklist table")

                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS vc_xp (
                        guild_id INTEGER,
                        user_id INTEGER,
                        xp INTEGER DEFAULT 0,
                        minutes INTEGER DEFAULT 0,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)

                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS vc_settings (
                        guild_id INTEGER PRIMARY KEY,
                        enabled INTEGER DEFAULT 1,
                        channel_id INTEGER,
                        level_message TEXT,
                        min_xp INTEGER DEFAULT 10,
                        max_xp INTEGER DEFAULT 20
                    )
                """)

                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS vc_level_rewards (
                        guild_id INTEGER,
                        level INTEGER,
                        role_id INTEGER,
                        remove_previous INTEGER DEFAULT 0,
                        PRIMARY KEY (guild_id, level)
                    )
                """)

                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS vc_xp_multipliers (
                        guild_id INTEGER,
                        target_id INTEGER,
                        target_type TEXT,
                        multiplier REAL,
                        PRIMARY KEY (guild_id, target_id, target_type)
                    )
                """)

                await db .execute ("""
                    CREATE TABLE IF NOT EXISTS leaderboard_settings (
                        guild_id INTEGER PRIMARY KEY,
                        channel_id INTEGER,
                        period TEXT,
                        weekday INTEGER,
                        time_ist TEXT,
                        last_posted TEXT,
                        live_channel_id INTEGER,
                        live_message_id INTEGER,
                        live_interval INTEGER DEFAULT 30,
                        live_last_posted TEXT
                    )
                """)

                await db .commit ()
                for column, ddl in (("live_interval", "INTEGER DEFAULT 30"), ("live_last_posted", "TEXT")):
                    async with db.cursor() as cursor:
                        await cursor.execute("PRAGMA table_info(leaderboard_settings)")
                        existing_columns = [col[1] for col in await cursor.fetchall()]
                        if column not in existing_columns:
                            await cursor.execute(f"ALTER TABLE leaderboard_settings ADD COLUMN {column} {ddl}")
                            logger.info(f"Added {column} column to leaderboard_settings table")

        except Exception as e :
            logger .error (f"Database initialization error: {e}")

    async def get_guild_settings (self ,guild_id :int )->dict :
        """Get guild leveling settings"""
        max_retries =5 
        for attempt in range (max_retries ):
            try :
                async with aiosqlite .connect ("db/leveling.db")as db :
                    async with db .execute ("SELECT * FROM leveling_settings WHERE guild_id = ?",(guild_id ,))as cursor :
                        row =await cursor .fetchone ()

                    if not row :

                        async with aiosqlite .connect ("db/leveling.db")as db :
                            await db .execute ("INSERT INTO leveling_settings (guild_id, enabled) VALUES (?, 0)",(guild_id ,))
                            await db .commit ()
                        return {
                        'enabled':False ,'channel_id':None ,
                        'level_message':'Congratulations {user}! You have reached level {level}!',
                        'embed_color':'#000000','level_image':None ,'thumbnail_enabled':True ,
                        'xp_per_message':20 ,'min_xp':15 ,'max_xp':25 ,'cooldown_seconds':60 ,
                        'dm_level_up':False 
                        }


                    embed_color =row [4 ]if len (row )>4 and row [4 ]is not None else 0 
                    if isinstance (embed_color ,int ):
                        color_hex =f"#{embed_color:06x}"
                    else :
                        color_hex ='#FF0000'


                    return {
                    'enabled':bool (row [1 ])if len (row )>1 else False ,
                    'channel_id':row [2 ]if len (row )>2 else None ,
                    'level_message':row [3 ]if len (row )>3 else 'Congratulations {user}! You have reached level {level}!',
                    'embed_color':color_hex ,
                    'level_image':row [5 ]if len (row )>5 else None ,
                    'thumbnail_enabled':bool (row [6 ])if len (row )>6 else True ,
                    'xp_per_message':row [7 ]if len (row )>7 else 20 ,
                    'min_xp':row [8 ]if len (row )>8 else 15 ,
                    'max_xp':row [9 ]if len (row )>9 else 25 ,
                    'cooldown_seconds':row [10 ]if len (row )>10 else 60 ,
                    'dm_level_up':bool (row [11 ])if len (row )>11 else False 
                    }

            except aiosqlite .OperationalError as e :
                if attempt <max_retries -1 :
                    logger .warning (f"Database locked, retrying... (attempt {attempt + 1})")
                    await asyncio .sleep (0.1 *(attempt +1 ))
                    continue 
                else :
                    logger .error (f"Database error after {max_retries} attempts: {e}")
                    break 
            except Exception as e :
                logger .error (f"Error getting guild settings: {e}")
                break 


        return {
        'enabled':False ,'channel_id':None ,
        'level_message':'Congratulations {user}! You have reached level {level}!',
        'embed_color':'#000000','level_image':None ,'thumbnail_enabled':True ,
        'xp_per_message':20 ,'min_xp':15 ,'max_xp':25 ,'cooldown_seconds':60 ,
        'dm_level_up':False 
        }

    async def is_blacklisted (self ,guild_id :int ,user_id :int ,channel_id :int )->bool :
        """Check if user or channel is blacklisted"""
        try :
            async with aiosqlite .connect ("db/leveling.db")as db :

                async with db .cursor ()as cursor :
                    await cursor .execute ("PRAGMA table_info(leveling_blacklist)")
                    columns =[col [1 ]for col in await cursor .fetchall ()]

                    if "target_type"not in columns :

                        logger .warning ("target_type column missing from leveling_blacklist table")
                        return False 


                async with db .execute (
                "SELECT 1 FROM leveling_blacklist WHERE guild_id = ? AND target_id = ? AND target_type = 'channel'",
                (guild_id ,channel_id )
                )as cursor :
                    if await cursor .fetchone ():
                        return True 


                guild =self .bot .get_guild (guild_id )
                if guild :
                    member =guild .get_member (user_id )
                    if member :
                        async with db .execute (
                        "SELECT target_id FROM leveling_blacklist WHERE guild_id = ? AND target_type = 'role'",
                        (guild_id ,)
                        )as cursor :
                            blacklisted_roles =[row [0 ]for row in await cursor .fetchall ()]
                            if any (role .id in blacklisted_roles for role in member .roles ):
                                return True 
                return False 
        except Exception as e :
            logger .error (f"Error checking blacklist: {e}")
            return False 

    async def get_xp_multiplier (self ,guild_id :int ,user_id :int ,channel_id :int )->float :
        """Get XP multiplier for user"""
        try :
            guild =self .bot .get_guild (guild_id )
            if not guild :
                return 1.0 

            member =guild .get_member (user_id )
            if not member :
                return 1.0 

            total_multiplier =1.0 
            async with aiosqlite .connect ("db/leveling.db")as db :

                async with db .execute (
                "SELECT target_id, multiplier FROM xp_multipliers WHERE guild_id = ? AND target_type = 'role'",
                (guild_id ,)
                )as cursor :
                    role_multipliers =await cursor .fetchall ()

                for role_id ,multiplier in role_multipliers :
                    if any (role .id ==role_id for role in member .roles ):
                        total_multiplier *=multiplier 


                async with db .execute (
                "SELECT multiplier FROM xp_multipliers WHERE guild_id = ? AND target_id = ? AND target_type = 'channel'",
                (guild_id ,channel_id )
                )as cursor :
                    channel_mult =await cursor .fetchone ()
                    if channel_mult :
                        total_multiplier *=channel_mult [0 ]

            return total_multiplier 
        except Exception as e :
            logger .error (f"Error getting XP multiplier: {e}")
            return 1.0 

    @commands .Cog .listener ()
    async def on_message (self ,message ):
        """Handle message XP tracking with independent message tracking system"""
        if message .author .bot or not message .guild :
            return 

        guild_id =message .guild .id 
        user_id =message .author .id 
        channel_id =message .channel .id 


        cooldown_key =f"{guild_id}_{user_id}"
        now =datetime .now ()

        if cooldown_key in self .message_cooldowns :
            if now <self .message_cooldowns [cooldown_key ]:
                return 

        try :
            settings =await self .get_guild_settings (guild_id )
            if not settings .get ('enabled',False ):
                return 

            if await self .is_blacklisted (guild_id ,user_id ,channel_id ):
                return 


            cooldown_seconds =settings .get ('cooldown_seconds',60 )
            self .message_cooldowns [cooldown_key ]=now +timedelta (seconds =cooldown_seconds )


            xp_low =settings .get ('min_xp')or settings .get ('xp_per_message')or 20 
            xp_high =settings .get ('max_xp')or xp_low 
            xp_low ,xp_high =int (xp_low ),int (xp_high )
            if xp_low >xp_high :
                xp_low ,xp_high =xp_high ,xp_low 
            final_xp =random .randint (max (1 ,xp_low ),max (1 ,xp_high ))


            multiplier =await self .get_xp_multiplier (guild_id ,user_id ,channel_id )
            if multiplier is None :
                multiplier =1.0 

            final_xp =int (final_xp *multiplier )


            async with aiosqlite .connect ("db/leveling.db")as db :
                async with db .execute (
                "SELECT xp, messages FROM user_xp WHERE guild_id = ? AND user_id = ?",
                (guild_id ,user_id )
                )as cursor :
                    row =await cursor .fetchone ()

                if row and len (row )>=2 :
                    current_xp =row [0 ]if row [0 ]is not None else 0 
                    current_messages =row [1 ]if row [1 ]is not None else 0 
                    old_level =calculate_level_from_xp (current_xp )
                    new_xp =current_xp +final_xp 
                    new_level =calculate_level_from_xp (new_xp )
                    new_messages =current_messages +1 

                    await db .execute ("""
                        UPDATE user_xp 
                        SET xp = ?, messages = ?, last_message_time = ?
                        WHERE guild_id = ? AND user_id = ?
                    """,(new_xp ,new_messages ,now .isoformat (),guild_id ,user_id ))
                else :
                    old_level =0 
                    new_level =calculate_level_from_xp (final_xp )
                    new_messages =1 

                    await db .execute ("""
                        INSERT INTO user_xp (guild_id, user_id, xp, messages, last_message_time)
                        VALUES (?, ?, ?, ?, ?)
                    """,(guild_id ,user_id ,final_xp ,new_messages ,now .isoformat ()))


                current_new_xp =new_xp if 'new_xp'in locals ()else final_xp 
                current_new_level =new_level if 'new_level'in locals ()else calculate_level_from_xp (final_xp )
                await db .execute ("""
                    INSERT OR REPLACE INTO users (guild_id, user_id, xp, level)
                    VALUES (?, ?, ?, ?)
                """,(guild_id ,user_id ,current_new_xp ,current_new_level ))

                await db .commit ()


            if new_level >old_level :
                await self .handle_level_up (message ,new_level ,settings )

        except Exception as e :
            logger .error (f"Error handling message XP: {e}")

    async def handle_level_up(self, message, new_level, settings):
        """Handle a chat level up."""
        await self.announce_level_up(
            message.guild, message.author, new_level, settings, message.channel
        )

    async def announce_level_up(self, guild, member, new_level, settings,
                                fallback_channel=None, *, destination=None,
                                earned_roles=None):
        """Render and send a level-up message.

        ``earned_roles`` is only passed by ``chatlevel test`` (so nothing is
        granted); when it is ``None`` the reward and level roles are applied
        first so ``{earned}`` can name them.
        """
        try:
            channel = destination

            if channel is None:
                channel_id = settings.get('channel_id')
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if channel and not channel.permissions_for(guild.me).send_messages:
                        logger.warning(f"No permission to send messages in configured level channel {channel_id}")
                        channel = None
                if channel is None and fallback_channel is not None:
                    channel = fallback_channel

            if channel is None:
                logger.error("No usable channel for the level-up message (set one with `chatlevel channel`)")
                return

            if earned_roles is None:
                earned_roles = await self.give_level_rewards(guild, member, new_level)
                earned_roles += await self.apply_level_roles(guild, member, new_level)

            await self._send_level_message(
                channel, guild, member, new_level,
                settings.get('level_message'), earned_roles,
            )

        except Exception as e:
            logger.error(f"Error handling level up: {e}")

    async def give_level_rewards(self, guild, member, level):
        """Give role rewards for reaching a level. Returns the roles added."""
        granted = []
        try:
            async with aiosqlite.connect("db/leveling.db") as db:
                async with db.execute(
                    "SELECT role_id, remove_previous FROM level_rewards WHERE guild_id = ? AND level <= ? ORDER BY level DESC",
                    (guild.id, level)
                ) as cursor:
                    rewards = await cursor.fetchall()

            for role_id, remove_previous in rewards:
                role = guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason=f"Level {level} reward")
                        granted.append(role)
                    except discord.Forbidden:
                        logger.warning(f"No permission to add reward role {role.name} to {member}")
                        continue
                    except discord.HTTPException as e:
                        logger.error(f"Failed to add reward role {role.name} to {member}: {e}")
                        continue

                    if remove_previous:
                        async with aiosqlite.connect("db/leveling.db") as db:
                            async with db.execute(
                                "SELECT role_id FROM level_rewards WHERE guild_id = ? AND level < ?",
                                (guild.id, level)
                            ) as cursor:
                                prev_rewards = await cursor.fetchall()

                        for prev_role_id, in prev_rewards:
                            prev_role = guild.get_role(prev_role_id)
                            if prev_role and prev_role in member.roles:
                                try:
                                    await member.remove_roles(prev_role, reason=f"Upgraded to level {level}")
                                except discord.HTTPException as e:
                                    logger.error(f"Failed to remove previous reward role {prev_role.name}: {e}")

        except Exception as e:
            logger.error(f"Error giving level rewards: {e}")
        return granted

    async def get_user_data (self ,guild_id :int ,user_id :int )->tuple :
        """Get user XP and level data"""
        try :
            async with aiosqlite .connect ("db/leveling.db")as db :
                async with db .execute (
                "SELECT xp, messages FROM user_xp WHERE guild_id = ? AND user_id = ?",
                (guild_id ,user_id )
                )as cursor :
                    row =await cursor .fetchone ()
                    if row :
                        xp ,messages =row 
                        level =calculate_level_from_xp (xp if xp is not None else 0 )
                        return xp if xp is not None else 0 ,level ,messages if messages is not None else 0 
                    return 0 ,0 ,0 
        except Exception as e :
            logger .error (f"Error getting user data: {e}")
            return 0 ,0 ,0 

    async def get_user_rank (self ,guild_id :int ,user_id :int )->int :
        """Get user's rank in the guild"""
        try :
            async with aiosqlite .connect ("db/leveling.db")as db :
                async with db .execute (
                "SELECT COUNT(*) + 1 FROM user_xp WHERE guild_id = ? AND xp > (SELECT COALESCE(xp, 0) FROM user_xp WHERE guild_id = ? AND user_id = ?)",
                (guild_id ,guild_id ,user_id )
                )as cursor :
                    rank =(await cursor .fetchone ())[0 ]
                    return rank 
        except Exception as e :
            logger .error (f"Error getting user rank: {e}")
            return 1 

    def create_simple_rank_card (self ,member ,xp ,level ,rank ,messages ):
        """Create a simple text-based rank card when PIL fails"""
        try :
            current_level ,progress ,needed =get_level_progress (xp )
            progress_bar =get_progress_bar (progress ,needed ,20 )

            rank_text =f"""
┌─────────────────────────────────────────┐
│ 🎮 RANK CARD - {member.display_name[:20]}
├─────────────────────────────────────────┤
│ 📊 Rank: #{rank:,}
│ ⭐ Level: {level:,}
│ 💬 Messages: {messages:,}
│ 🎯 XP: {xp:,}
├─────────────────────────────────────────┤
│ Progress to Level {level + 1}:
│ {progress_bar}
│ {progress:,} / {needed:,} XP
└─────────────────────────────────────────┘
            """
            return rank_text .strip ()
        except Exception as e :
            logger .error (f"Error creating simple rank card: {e}")
            return f"**{member.display_name}** - Level {level} - Rank #{rank}"

    async def create_rank_card (self ,member ,guild_id ):
        """Create rank card with random design selection - fallback to text if PIL fails"""
        try :
            xp ,level ,messages =await self .get_user_data (guild_id ,member .id )
            rank =await self .get_user_rank (guild_id ,member .id )


            if PIL_AVAILABLE :
                try :

                    design_number =random .randint (1 ,7 )
                    return await self .create_rank_card_design (member ,xp ,level ,rank ,messages ,design_number )

                except Exception as e :
                    logger .error (f"PIL error, falling back to text: {e}")

                    return self .create_simple_rank_card (member ,xp ,level ,rank ,messages )
            else :

                logger .warning ("PIL not available, using text-based rank card")
                return self .create_simple_rank_card (member ,xp ,level ,rank ,messages )

        except Exception as e :
            logger .error (f"Error creating rank card: {e}")
            return None 

    async def create_rank_card_design (self ,member ,xp ,level ,rank ,messages ,design_number ):
        """Create specific rank card design based on design number"""
        current_level ,progress ,needed =get_level_progress (xp )
        width ,height =900 ,300 


        try :
            font_large =ImageFont .truetype ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",28 )
            font_medium =ImageFont .truetype ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",20 )
            font_small =ImageFont .truetype ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",16 )
        except (OSError ,IOError ):
            font_large =ImageFont .load_default ()
            font_medium =ImageFont .load_default ()
            font_small =ImageFont .load_default ()

        if design_number ==1 :
            return await self .create_classic_design (member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )
        elif design_number ==2 :
            return await self .create_neon_design (member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )
        elif design_number ==3 :
            return await self .create_space_design (member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )
        elif design_number ==4 :
            return await self .create_minimal_design (member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )
        elif design_number ==5 :
            return await self .create_gaming_design (member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )
        elif design_number ==6 :
            return await self .create_elegant_design (member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )
        else :
            return await self .create_cyberpunk_design (member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )

    async def create_classic_design (self ,member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Original design with diagonal gradient"""
        img =Image .new ('RGB',(width ,height ),(32 ,34 ,37 ))
        draw =ImageDraw .Draw (img )


        color_schemes =[
        [(45 ,52 ,54 ),(99 ,110 ,114 )],
        [(74 ,144 ,226 ),(80 ,227 ,194 )],
        [(245 ,166 ,35 ),(242 ,112 ,156 )],
        [(165 ,94 ,234 ),(74 ,144 ,226 )],
        [(255 ,118 ,117 ),(255 ,204 ,128 )],
        [(18 ,194 ,233 ),(196 ,113 ,237 )],
        ]

        scheme =color_schemes [level %len (color_schemes )]


        for x in range (width ):
            for y in range (height ):
                factor_x =x /width 
                factor_y =y /height 
                factor =(factor_x +factor_y )/2 

                r =int (scheme [0 ][0 ]+(scheme [1 ][0 ]-scheme [0 ][0 ])*factor )
                g =int (scheme [0 ][1 ]+(scheme [1 ][1 ]-scheme [0 ][1 ])*factor )
                b =int (scheme [0 ][2 ]+(scheme [1 ][2 ]-scheme [0 ][2 ])*factor )
                draw .point ((x ,y ),fill =(r ,g ,b ))


        draw .rounded_rectangle ((15 ,15 ,width -15 ,height -15 ),radius =20 ,fill =(0 ,0 ,0 ,100 ))
        draw .rounded_rectangle ((15 ,15 ,width -15 ,height -15 ),radius =20 ,outline =(255 ,255 ,255 ,50 ),width =2 )


        await self .add_avatar_and_content_classic (draw ,member ,level ,rank ,messages ,xp ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )


        img_bytes =io .BytesIO ()
        img .save (img_bytes ,format ='PNG')
        img_bytes .seek (0 )
        img .close ()
        return img_bytes 

    async def create_neon_design (self ,member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Neon cyberpunk style design"""
        img =Image .new ('RGB',(width ,height ),(10 ,10 ,25 ))
        draw =ImageDraw .Draw (img )


        grid_color =(0 ,255 ,255 ,30 )
        for x in range (0 ,width ,50 ):
            draw .line ([(x ,0 ),(x ,height )],fill =grid_color ,width =1 )
        for y in range (0 ,height ,50 ):
            draw .line ([(0 ,y ),(width ,y )],fill =grid_color ,width =1 )


        for i in range (5 ):
            draw .rounded_rectangle ((15 -i ,15 -i ,width -15 +i ,height -15 +i ),radius =20 +i ,outline =(0 ,255 ,255 ,50 -i *10 ),width =1 )


        draw .rounded_rectangle ((20 ,20 ,width -20 ,height -20 ),radius =15 ,fill =(5 ,5 ,20 ))


        await self .add_avatar_and_content_neon (draw ,member ,level ,rank ,messages ,xp ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )

        img_bytes =io .BytesIO ()
        img .save (img_bytes ,format ='PNG')
        img_bytes .seek (0 )
        img .close ()
        return img_bytes 

    async def create_space_design (self ,member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Space theme with stars and nebula"""
        img =Image .new ('RGB',(width ,height ),(5 ,5 ,20 ))
        draw =ImageDraw .Draw (img )


        for i in range (100 ):
            x =random .randint (0 ,width )
            y =random .randint (0 ,height )
            size =random .randint (1 ,3 )
            brightness =random .randint (150 ,255 )
            draw .ellipse ((x ,y ,x +size ,y +size ),fill =(brightness ,brightness ,brightness ))


        for x in range (0 ,width ,20 ):
            for y in range (0 ,height ,20 ):
                if random .random ()<0.3 :
                    color_r =random .randint (50 ,150 )
                    color_g =random .randint (0 ,100 )
                    color_b =random .randint (100 ,200 )
                    draw .ellipse ((x ,y ,x +30 ,y +30 ),fill =(color_r ,color_g ,color_b ,30 ))


        draw .rounded_rectangle ((20 ,20 ,width -20 ,height -20 ),radius =15 ,fill =(0 ,0 ,0 ,150 ))

        await self .add_avatar_and_content_space (draw ,member ,level ,rank ,messages ,xp ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )

        img_bytes =io .BytesIO ()
        img .save (img_bytes ,format ='PNG')
        img_bytes .seek (0 )
        img .close ()
        return img_bytes 

    async def create_minimal_design (self ,member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Clean minimal design"""
        img =Image .new ('RGB',(width ,height ),(248 ,249 ,250 ))
        draw =ImageDraw .Draw (img )


        draw .rounded_rectangle ((10 ,10 ,width -10 ,height -10 ),radius =15 ,outline =(220 ,220 ,220 ),width =2 ,fill =(255 ,255 ,255 ))


        draw .rounded_rectangle ((12 ,12 ,width -8 ,height -8 ),radius =15 ,outline =(240 ,240 ,240 ),width =1 )

        await self .add_avatar_and_content_minimal (draw ,member ,level ,rank ,messages ,xp ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )

        img_bytes =io .BytesIO ()
        img .save (img_bytes ,format ='PNG')
        img_bytes .seek (0 )
        img .close ()
        return img_bytes 

    async def create_gaming_design (self ,member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Gaming RGB style design"""
        img =Image .new ('RGB',(width ,height ),(20 ,20 ,20 ))
        draw =ImageDraw .Draw (img )


        colors =[(255 ,0 ,0 ),(255 ,127 ,0 ),(255 ,255 ,0 ),(0 ,255 ,0 ),(0 ,0 ,255 ),(139 ,0 ,255 )]
        for i ,color in enumerate (colors ):
            offset =i *2 
            draw .rounded_rectangle ((10 +offset ,10 +offset ,width -10 -offset ,height -10 -offset ),
            radius =20 -offset ,outline =color ,width =2 )


        draw .rounded_rectangle ((25 ,25 ,width -25 ,height -25 ),radius =10 ,fill =(15 ,15 ,15 ))

        await self .add_avatar_and_content_gaming (draw ,member ,level ,rank ,messages ,xp ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small )

        img_bytes =io .BytesIO ()
        img .save (img_bytes ,format ='PNG')
        img_bytes .seek (0 )
        img .close ()
        return img_bytes 

    async def create_elegant_design (self ,member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Elegant gold and black design"""
        img =Image .new ('RGB',(width ,height ),(25 ,25 ,25 ))
        draw =ImageDraw .Draw (img )


        for i in range (10 ):
            alpha =255 -(i *25 )
            color =(255 ,215 ,0 ,alpha )
            draw .rounded_rectangle ((5 +i ,5 +i ,width -5 -i ,height -5 -i ),radius =20 +i ,outline =color ,width =1 )


        draw .rounded_rectangle ((20 ,20 ,width -20 ,height -20 ),radius =15 ,fill =(35 ,35 ,35 ))

        await self .add_avatar_and_content_elegant (draw ,member ,xp ,progress ,needed ,messages ,level ,rank ,width ,height ,font_large ,font_medium ,font_small )

        img_bytes =io .BytesIO ()
        img .save (img_bytes ,format ='PNG')
        img_bytes .seek (0 )
        img .close ()
        return img_bytes 

    async def create_cyberpunk_design (self ,member ,xp ,level ,rank ,messages ,current_level ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Cyberpunk style design"""
        img =Image .new ('RGB',(width ,height ),(15 ,15 ,15 ))
        draw =ImageDraw .Draw (img )


        line_color =(75 ,0 ,130 )
        for i in range (20 ):
            y =int (height /20 *i )
            draw .line ((0 ,y ,width ,y ),fill =line_color ,width =1 )


        panel_color =(25 ,25 ,25 )
        draw .rounded_rectangle ((20 ,20 ,width -20 ,height -20 ),radius =15 ,fill =panel_color )


        await self .add_avatar_and_content_cyberpunk (draw ,member ,xp ,progress ,needed ,messages ,level ,rank ,width ,height ,font_large ,font_medium ,font_small )

        img_bytes =io .BytesIO ()
        img .save (img_bytes ,format ='PNG')
        img_bytes .seek (0 )
        img .close ()
        return img_bytes 

    async def add_avatar_and_content_classic (self ,draw ,member ,level ,rank ,messages ,xp ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Add avatar and content for classic design"""

        avatar_size =120 
        avatar_x ,avatar_y =30 ,90 

        try :
            avatar_url =str (member .display_avatar .with_size (256 ).url )
            response =requests .get (avatar_url ,timeout =10 )
            if response .status_code ==200 :
                avatar_img =Image .open (io .BytesIO (response .content ))
                avatar_img =avatar_img .resize ((avatar_size ,avatar_size ))

                mask =Image .new ('L',(avatar_size ,avatar_size ),0 )
                mask_draw =ImageDraw .Draw (mask )
                mask_draw .ellipse ((0 ,0 ,avatar_size ,avatar_size ),fill =255 )

                draw .ellipse ((avatar_x -3 ,avatar_y -3 ,avatar_x +avatar_size +3 ,avatar_y +avatar_size +3 ),fill =(255 ,255 ,255 ))

                avatar_img .putalpha (mask )
                img =draw ._image 
                img .paste (avatar_img ,(avatar_x ,avatar_y ),avatar_img )
            else :
                raise Exception ("Failed to download avatar")
        except Exception as e :
            draw .ellipse ((avatar_x -3 ,avatar_y -3 ,avatar_x +avatar_size +3 ,avatar_y +avatar_size +3 ),fill =(255 ,255 ,255 ))
            draw .ellipse ((avatar_x ,avatar_y ,avatar_x +avatar_size ,avatar_y +avatar_size ),fill =(64 ,68 ,75 ))
            draw .text ((avatar_x +avatar_size //2 -20 ,avatar_y +avatar_size //2 -20 ),"👤",font =font_large ,fill =(255 ,255 ,255 ))


        info_x =180 
        username =member .display_name [:18 ]

        draw .text ((info_x +2 ,42 ),username ,font =font_large ,fill =(0 ,0 ,0 ))
        draw .text ((info_x ,40 ),username ,font =font_large ,fill =(255 ,255 ,255 ))

        draw .text ((info_x +2 ,82 ),f"🏆 Level {level}",font =font_medium ,fill =(0 ,0 ,0 ))
        draw .text ((info_x ,80 ),f"🏆 Level {level}",font =font_medium ,fill =(255 ,215 ,0 ))

        draw .text ((info_x +2 ,112 ),f"📊 Rank #{rank}",font =font_medium ,fill =(0 ,0 ,0 ))
        draw .text ((info_x ,110 ),f"📊 Rank #{rank}",font =font_medium ,fill =(135 ,206 ,250 ))


        bar_x ,bar_y =info_x ,150 
        bar_width ,bar_height =500 ,25 

        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =12 ,fill =(32 ,34 ,37 ))
        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =12 ,outline =(128 ,128 ,128 ),width =1 )

        if needed >0 :
            progress_width =int ((progress /needed )*bar_width )
            if progress_width >0 :
                for i in range (progress_width ):
                    factor =i /progress_width if progress_width >0 else 0 
                    r =int (100 +(255 -100 )*factor )
                    g =int (150 +(105 -150 )*factor )
                    b =int (255 -50 *factor )
                    draw .line ([(bar_x +i ,bar_y +2 ),(bar_x +i ,bar_y +bar_height -2 )],fill =(r ,g ,b ))

        xp_text =f"{progress:,} / {needed:,} XP"
        text_bbox =draw .textbbox ((0 ,0 ),xp_text ,font =font_small )
        text_width =text_bbox [2 ]-text_bbox [0 ]
        text_x =bar_x +(bar_width -text_width )//2 
        draw .text ((text_x +1 ,bar_y +6 ),xp_text ,font =font_small ,fill =(0 ,0 ,0 ))
        draw .text ((text_x ,bar_y +5 ),xp_text ,font =font_small ,fill =(255 ,255 ,255 ))


        stats_x =720 
        draw .text ((stats_x +1 ,81 ),f"💬 Messages",font =font_small ,fill =(0 ,0 ,0 ))
        draw .text ((stats_x ,80 ),f"💬 Messages",font =font_small ,fill =(255 ,255 ,255 ))
        draw .text ((stats_x +1 ,101 ),f"{messages:,}",font =font_medium ,fill =(0 ,0 ,0 ))
        draw .text ((stats_x ,100 ),f"{messages:,}",font =font_medium ,fill =(0 ,255 ,127 ))

        draw .text ((stats_x +1 ,131 ),f"⭐ Total XP",font =font_small ,fill =(0 ,0 ,0 ))
        draw .text ((stats_x ,130 ),f"⭐ Total XP",font =font_small ,fill =(255 ,255 ,255 ))
        draw .text ((stats_x +1 ,151 ),f"{xp:,}",font =font_medium ,fill =(0 ,0 ,0 ))
        draw .text ((stats_x ,150 ),f"{xp:,}",font =font_medium ,fill =(255 ,165 ,0 ))

        percentage =(progress /needed *100 )if needed >0 else 100 
        draw .text ((stats_x +1 ,181 ),f"📈 Progress",font =font_small ,fill =(0 ,0 ,0 ))
        draw .text ((stats_x ,180 ),f"📈 Progress",font =font_small ,fill =(255 ,255 ,255 ))
        draw .text ((stats_x +1 ,201 ),f"{percentage:.1f}%",font =font_medium ,fill =(0 ,0 ,0 ))
        draw .text ((stats_x ,200 ),f"{percentage:.1f}%",font =font_medium ,fill =(255 ,105 ,180 ))

        if level >=10 :
            sparkle_positions =[(50 ,50 ),(850 ,50 ),(50 ,250 ),(850 ,250 )]
            for pos in sparkle_positions :
                draw .text (pos ,"✨",font =font_small ,fill =(255 ,255 ,255 ))

    async def add_avatar_and_content_neon (self ,draw ,member ,level ,rank ,messages ,xp ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Add avatar and content for neon design"""
        avatar_size =100 
        avatar_x ,avatar_y =40 ,100 


        for i in range (3 ):
            draw .ellipse ((avatar_x -5 -i ,avatar_y -5 -i ,avatar_x +avatar_size +5 +i ,avatar_y +avatar_size +5 +i ),outline =(0 ,255 ,255 ),width =1 )

        try :
            avatar_url =str (member .display_avatar .with_size (256 ).url )
            response =requests .get (avatar_url ,timeout =10 )
            if response .status_code ==200 :
                avatar_img =Image .open (io .BytesIO (response .content ))
                avatar_img =avatar_img .resize ((avatar_size ,avatar_size ))

                mask =Image .new ('L',(avatar_size ,avatar_size ),0 )
                mask_draw =ImageDraw .Draw (mask )
                mask_draw .ellipse ((0 ,0 ,avatar_size ,avatar_size ),fill =255 )

                avatar_img .putalpha (mask )
                img =draw ._image 
                img .paste (avatar_img ,(avatar_x ,avatar_y ),avatar_img )
            else :
                raise Exception ("Failed to download avatar")
        except Exception as e :
            draw .ellipse ((avatar_x ,avatar_y ,avatar_x +avatar_size ,avatar_y +avatar_size ),fill =(0 ,50 ,50 ))
            draw .text ((avatar_x +avatar_size //2 -15 ,avatar_y +avatar_size //2 -15 ),"👤",font =font_medium ,fill =(0 ,255 ,255 ))


        info_x =170 
        username =member .display_name [:15 ]


        for offset in [(2 ,2 ),(1 ,1 ),(0 ,0 )]:
            color =(0 ,255 ,255 )if offset ==(0 ,0 )else (0 ,100 ,100 )
            draw .text ((info_x +offset [0 ],50 +offset [1 ]),username ,font =font_large ,fill =color )
            draw .text ((info_x +offset [0 ],85 +offset [1 ]),f"⚡ Level {level}",font =font_medium ,fill =color )
            draw .text ((info_x +offset [0 ],115 +offset [1 ]),f"🎯 Rank #{rank}",font =font_medium ,fill =color )


        bar_x ,bar_y =info_x ,160 
        bar_width ,bar_height =480 ,20 

        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =10 ,fill =(0 ,20 ,20 ))
        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =10 ,outline =(0 ,255 ,255 ),width =2 )

        if needed >0 :
            progress_width =int ((progress /needed )*bar_width )
            if progress_width >0 :
                draw .rounded_rectangle ((bar_x +2 ,bar_y +2 ,bar_x +progress_width -2 ,bar_y +bar_height -2 ),radius =8 ,fill =(0 ,255 ,255 ))

        xp_text =f"{progress:,} / {needed:,} XP"
        text_bbox =draw .textbbox ((0 ,0 ),xp_text ,font =font_small )
        text_width =text_bbox [2 ]-text_bbox [0 ]
        text_x =bar_x +(bar_width -text_width )//2 
        draw .text ((text_x ,bar_y +2 ),xp_text ,font =font_small ,fill =(255 ,255 ,255 ))


        stats_x =700 
        stats_y =80 
        draw .text ((stats_x ,stats_y ),f"💬 {messages:,}",font =font_small ,fill =(0 ,255 ,255 ))
        draw .text ((stats_x ,stats_y +25 ),f"⭐ {xp:,} XP",font =font_small ,fill =(0 ,255 ,255 ))

        percentage =(progress /needed *100 )if needed >0 else 100 
        draw .text ((stats_x ,stats_y +50 ),f"📈 {percentage:.1f}%",font =font_small ,fill =(0 ,255 ,255 ))

    async def add_avatar_and_content_space (self ,draw ,member ,level ,rank ,messages ,xp ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Add avatar and content for space design"""
        avatar_size =110 
        avatar_x ,avatar_y =35 ,95 


        for i in range (5 ):
            alpha =100 -(i *20 )
            draw .ellipse ((avatar_x -5 -i ,avatar_y -5 -i ,avatar_x +avatar_size +5 +i ,avatar_y +avatar_size +5 +i ),
            outline =(100 ,150 ,255 ,alpha ),width =1 )

        try :
            avatar_url =str (member .display_avatar .with_size (256 ).url )
            response =requests .get (avatar_url ,timeout =10 )
            if response .status_code ==200 :
                avatar_img =Image .open (io .BytesIO (response .content ))
                avatar_img =avatar_img .resize ((avatar_size ,avatar_size ))

                mask =Image .new ('L',(avatar_size ,avatar_size ),0 )
                mask_draw =ImageDraw .Draw (mask )
                mask_draw .ellipse ((0 ,0 ,avatar_size ,avatar_size ),fill =255 )

                avatar_img .putalpha (mask )
                img =draw ._image 
                img .paste (avatar_img ,(avatar_x ,avatar_y ),avatar_img )
            else :
                raise Exception ("Failed to download avatar")
        except Exception as e :
            draw .ellipse ((avatar_x ,avatar_y ,avatar_x +avatar_size ,avatar_y +avatar_size ),fill =(20 ,30 ,60 ))
            draw .text ((avatar_x +avatar_size //2 -15 ,avatar_y +avatar_size //2 -15 ),"🚀",font =font_medium ,fill =(255 ,255 ,255 ))


        info_x =175 
        username =member .display_name [:16 ]

        draw .text ((info_x ,45 ),username ,font =font_large ,fill =(255 ,255 ,255 ))
        draw .text ((info_x ,80 ),f"🌟 Level {level}",font =font_medium ,fill =(255 ,215 ,0 ))
        draw .text ((info_x ,110 ),f"🛸 Rank #{rank}",font =font_medium ,fill =(100 ,200 ,255 ))


        bar_x ,bar_y =info_x ,155 
        bar_width ,bar_height =490 ,22 

        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =11 ,fill =(10 ,10 ,30 ))
        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =11 ,outline =(100 ,150 ,255 ),width =1 )

        if needed >0 :
            progress_width =int ((progress /needed )*bar_width )
            if progress_width >0 :

                for i in range (progress_width ):
                    factor =i /progress_width if progress_width >0 else 0 
                    r =int (50 +(200 *factor ))
                    g =int (100 +(150 *factor ))
                    b =255 
                    draw .line ([(bar_x +i ,bar_y +2 ),(bar_x +i ,bar_y +bar_height -2 )],fill =(r ,g ,b ))

        xp_text =f"{progress:,} / {needed:,} XP"
        text_bbox =draw .textbbox ((0 ,0 ),xp_text ,font =font_small )
        text_width =text_bbox [2 ]-text_bbox [0 ]
        text_x =bar_x +(bar_width -text_width )//2 
        draw .text ((text_x ,bar_y +3 ),xp_text ,font =font_small ,fill =(255 ,255 ,255 ))


        stats_x =720 
        draw .text ((stats_x ,85 ),f"📡 Messages",font =font_small ,fill =(200 ,200 ,255 ))
        draw .text ((stats_x ,105 ),f"{messages:,}",font =font_medium ,fill =(255 ,255 ,255 ))
        draw .text ((stats_x ,135 ),f"⭐ Total XP",font =font_small ,fill =(200 ,200 ,255 ))
        draw .text ((stats_x ,155 ),f"{xp:,}",font =font_medium ,fill =(255 ,215 ,0 ))

        percentage =(progress /needed *100 )if needed >0 else 100 
        draw .text ((stats_x ,185 ),f"🌌 {percentage:.1f}%",font =font_small ,fill =(100 ,200 ,255 ))

    async def add_avatar_and_content_minimal (self ,draw ,member ,level ,rank ,messages ,xp ,progress ,needed ,width ,height ,font_large ,font_medium ,font_small ):
        """Add avatar and content for minimal design"""
        avatar_size =100 
        avatar_x ,avatar_y =40 ,100 


        draw .ellipse ((avatar_x -2 ,avatar_y -2 ,avatar_x +avatar_size +2 ,avatar_y +avatar_size +2 ),outline =(200 ,200 ,200 ),width =2 )

        try :
            avatar_url =str (member .display_avatar .with_size (256 ).url )
            response =requests .get (avatar_url ,timeout =10 )
            if response .status_code ==200 :
                avatar_img =Image .open (io .BytesIO (response .content ))
                avatar_img =avatar_img .resize ((avatar_size ,avatar_size ))

                mask =Image .new ('L',(avatar_size ,avatar_size ),0 )
                mask_draw =ImageDraw .Draw (mask )
                mask_draw .ellipse ((0 ,0 ,avatar_size ,avatar_size ),fill =255 )

                avatar_img .putalpha (mask )
                img =draw ._image 
                img .paste (avatar_img ,(avatar_x ,avatar_y ),avatar_img )
            else :
                raise Exception ("Failed to download avatar")
        except Exception as e :
            draw .ellipse ((avatar_x ,avatar_y ,avatar_x +avatar_size ,avatar_y +avatar_size ),fill =(240 ,240 ,240 ))
            draw .text ((avatar_x +avatar_size //2 -15 ,avatar_y +avatar_size //2 -15 ),"👤",font =font_medium ,fill =(100 ,100 ,100 ))


        info_x =170 
        username =member .display_name [:18 ]

        draw .text ((info_x ,50 ),username ,font =font_large ,fill =(50 ,50 ,50 ))
        draw .text ((info_x ,85 ),f"Level {level}",font =font_medium ,fill =(100 ,100 ,100 ))
        draw .text ((info_x ,115 ),f"Rank #{rank}",font =font_medium ,fill =(150 ,150 ,150 ))


        bar_x ,bar_y =info_x ,160 
        bar_width ,bar_height =480 ,18 

        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =9 ,fill =(240 ,240 ,240 ))
        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =9 ,outline =(200 ,200 ,200 ),width =1 )

        if needed >0 :
            progress_width =int ((progress /needed )*bar_width )
            if progress_width >0 :
                draw .rounded_rectangle ((bar_x +2 ,bar_y +2 ,bar_x +progress_width -2 ,bar_y +bar_height -2 ),radius =7 ,fill =(220 ,220 ,220 ))

        xp_text =f"{progress:,} / {needed:,} XP"
        text_bbox =draw .textbbox ((0 ,0 ),xp_text ,font =font_small )
        text_width =text_bbox [2 ]-text_bbox [0 ]
        text_x =bar_x +(bar_width -text_width )//2 
        draw .text ((text_x ,bar_y +2 ),xp_text ,font =font_small ,fill =(100 ,100 ,100 ))


        stats_x =700 
        draw .text ((stats_x ,85 ),f"Messages: {messages:,}",font =font_small ,fill =(120 ,120 ,120 ))
        draw .text ((stats_x ,115 ),f"Total XP: {xp:,}",font =font_small ,fill =(120 ,120 ,120 ))

        percentage =(progress /needed *100 )if needed >0 else 100 
        draw .text ((stats_x ,145 ),f"Progress: {percentage:.1f}%",font =font_small ,fill =(120 ,120 ,120 ))

    async def add_avatar_and_content_gaming (self ,draw ,member ,xp ,progress ,needed ,messages ,level ,rank ,width ,height ,font_large ,font_medium ,font_small ):
        """Add avatar and content for gaming design"""
        avatar_size =110 
        avatar_x ,avatar_y =35 ,95 


        colors =[(255 ,0 ,0 ),(0 ,255 ,0 ),(0 ,0 ,255 )]
        for i ,color in enumerate (colors ):
            offset =i *2 
            draw .ellipse ((avatar_x -5 -offset ,avatar_y -5 -offset ,avatar_x +avatar_size +5 +offset ,avatar_y +avatar_size +5 +offset ),outline =color ,width =1 )

        try :
            avatar_url =str (member .display_avatar .with_size (256 ).url )
            response =requests .get (avatar_url ,timeout =10 )
            if response .status_code ==200 :
                avatar_img =Image .open (io .BytesIO (response .content ))
                avatar_img =avatar_img .resize ((avatar_size ,avatar_size ))

                mask =Image .new ('L',(avatar_size ,avatar_size ),0 )
                mask_draw =ImageDraw .Draw (mask )
                mask_draw .ellipse ((0 ,0 ,avatar_size ,avatar_size ),fill =255 )

                avatar_img .putalpha (mask )
                img =draw ._image 
                img .paste (avatar_img ,(avatar_x ,avatar_y ),avatar_img )
            else :
                raise Exception ("Failed to download avatar")
        except Exception as e :
            draw .ellipse ((avatar_x ,avatar_y ,avatar_x +avatar_size ,avatar_y +avatar_size ),fill =(30 ,30 ,30 ))
            draw .text ((avatar_x +avatar_size //2 -15 ,avatar_y +avatar_size //2 -15 ),"🎮",font =font_medium ,fill =(200 ,200 ,200 ))


        info_x =175 
        username =member .display_name [:16 ]

        draw .text ((info_x ,45 ),username ,font =font_large ,fill =(200 ,200 ,200 ))
        draw .text ((info_x ,80 ),f"Level {level}",font =font_medium ,fill =(150 ,150 ,150 ))
        draw .text ((info_x ,110 ),f"Rank #{rank}",font =font_medium ,fill =(100 ,100 ,100 ))


        bar_x ,bar_y =info_x ,155 
        bar_width ,bar_height =490 ,22 

        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =11 ,fill =(30 ,30 ,30 ))
        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =11 ,outline =(80 ,80 ,80 ),width =1 )

        if needed >0 :
            progress_width =int ((progress /needed )*bar_width )
            if progress_width >0 :

                for i in range (progress_width ):
                    factor =i /progress_width if progress_width >0 else 0 
                    r =int (50 +(150 *factor ))
                    g =int (100 +(100 *factor ))
                    b =200 
                    draw .line ([(bar_x +i ,bar_y +2 ),(bar_x +i ,bar_y +bar_height -2 )],fill =(r ,g ,b ))

        xp_text =f"{progress:,} / {needed:,} XP"
        text_bbox =draw .textbbox ((0 ,0 ),xp_text ,font =font_small )
        text_width =text_bbox [2 ]-text_bbox [0 ]
        text_x =bar_x +(bar_width -text_width )//2 
        draw .text ((text_x ,bar_y +3 ),xp_text ,font =font_small ,fill =(200 ,200 ,200 ))


        stats_x =720 
        draw .text ((stats_x ,85 ),f"Messages: {messages:,}",font =font_small ,fill =(150 ,150 ,150 ))
        draw .text ((stats_x ,115 ),f"Total XP: {xp:,}",font =font_small ,fill =(150 ,150 ,150 ))

        percentage =(progress /needed *100 )if needed >0 else 100 
        draw .text ((stats_x ,145 ),f"Progress: {percentage:.1f}%",font =font_small ,fill =(150 ,150 ,150 ))

    async def add_avatar_and_content_elegant (self ,draw ,member ,xp ,progress ,needed ,messages ,level ,rank ,width ,height ,font_large ,font_medium ,font_small ):
        """Add avatar and content for elegant design"""
        avatar_size =110 
        avatar_x ,avatar_y =35 ,95 


        for i in range (3 ):
            alpha =150 -(i *50 )
            draw .ellipse ((avatar_x -4 -i ,avatar_y -4 -i ,avatar_x +avatar_size +4 +i ,avatar_y +avatar_size +4 +i ),outline =(255 ,215 ,0 ,alpha ),width =1 )

        try :
            avatar_url =str (member .display_avatar .with_size (256 ).url )
            response =requests .get (avatar_url ,timeout =10 )
            if response .status_code ==200 :
                avatar_img =Image .open (io .BytesIO (response .content ))
                avatar_img =avatar_img .resize ((avatar_size ,avatar_size ))

                mask =Image .new ('L',(avatar_size ,avatar_size ),0 )
                mask_draw =ImageDraw .Draw (mask )
                mask_draw .ellipse ((0 ,0 ,avatar_size ,avatar_size ),fill =255 )

                avatar_img .putalpha (mask )
                img =draw ._image 
                img .paste (avatar_img ,(avatar_x ,avatar_y ),avatar_img )
            else :
                raise Exception ("Failed to download avatar")
        except Exception as e :
            draw .ellipse ((avatar_x ,avatar_y ,avatar_x +avatar_size ,avatar_y +avatar_size ),fill =(45 ,45 ,45 ))
            draw .text ((avatar_x +avatar_size //2 -15 ,avatar_y +avatar_size //2 -15 ),"👑",font =font_medium ,fill =(255 ,215 ,0 ))


        info_x =175 
        username =member .display_name [:16 ]

        draw .text ((info_x ,45 ),username ,font =font_large ,fill =(230 ,230 ,230 ))
        draw .text ((info_x ,80 ),f"Level {level}",font =font_medium ,fill =(200 ,170 ,0 ))
        draw .text ((info_x ,110 ),f"Rank #{rank}",font =font_medium ,fill =(180 ,180 ,180 ))


        bar_x ,bar_y =info_x ,155 
        bar_width ,bar_height =490 ,22 

        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =11 ,fill =(40 ,40 ,40 ))
        draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),radius =11 ,outline =(100 ,80 ,0 ),width =1 )

        if needed >0 :
            progress_width =int ((progress /needed )*bar_width )
            if progress_width >0 :

                for i in range (progress_width ):
                    factor =i /progress_width if progress_width >0 else 0 
                    r =255 
                    g =int (150 +(65 *factor ))
                    b =0 
                    draw .line ([(bar_x +i ,bar_y +2 ),(bar_x +i ,bar_y +bar_height -2 )],fill =(r ,g ,b ))

        xp_text =f"{progress:,} / {needed:,} XP"
        text_bbox =draw .textbbox ((0 ,0 ),xp_text ,font =font_small )
        text_width =text_bbox [2 ]-text_bbox [0 ]
        text_x =bar_x +(bar_width -text_width )//2 
        draw .text ((text_x ,bar_y +3 ),xp_text ,font =font_small ,fill =(220 ,220 ,220 ))


        stats_x =720 
        draw .text ((stats_x ,85 ),f"Messages: {messages:,}",font =font_small ,fill =(180 ,180 ,180 ))
        draw .text ((stats_x ,115 ),f"Total XP: {xp:,}",font =font_small ,fill =(255 ,215 ,0 ))

        percentage =(progress /needed *100 )if needed >0 else 100 
        draw .text ((stats_x ,145 ),f"Progress: {percentage:.1f}%",font =font_small ,fill =(200 ,200 ,200 ))

    async def add_avatar_and_content_cyberpunk (self ,draw ,member ,xp ,progress ,needed ,messages ,level ,rank ,width ,height ,font_large ,font_medium ,font_small ):
        """Add avatar and content for cyberpunk design"""
        avatar_size =100 
        avatar_x ,avatar_y =40 ,100 


        try :
            avatar_url =str (member .display_avatar .with_size (256 ).url )
            response =requests .get (avatar_url ,timeout =10 )
            if response .status_code ==200 :
                avatar_img =Image .open (io .BytesIO (response .content ))
                avatar_img =avatar_img .resize ((avatar_size ,avatar_size ))

                mask =Image .new ('L',(avatar_size ,avatar_size ),0 )
                mask_draw =ImageDraw .Draw (mask )
                mask_draw .rectangle ((0 ,0 ,avatar_size ,avatar_size ),fill =255 )

                avatar_img .putalpha (mask )
                img =draw ._image 
                img .paste (avatar_img ,(avatar_x ,avatar_y ),avatar_img )
            else :
                raise Exception ("Failed to download avatar")
        except Exception as e :
            draw .rectangle ((avatar_x ,avatar_y ,avatar_x +avatar_size ,avatar_y +avatar_size ),fill =(45 ,45 ,45 ))
            draw .text ((avatar_x +avatar_size //2 -15 ,avatar_y +avatar_size //2 -15 ),"👤",font =font_medium ,fill =(148 ,0 ,211 ))


        text_color =(148 ,0 ,211 )
        info_x =170 
        username =member .display_name [:15 ]

        draw .text ((info_x ,50 ),username ,font =font_large ,fill =text_color )
        draw .text ((info_x ,85 ),f"Level {level}",font =font_medium ,fill =text_color )
        draw .text ((info_x ,115 ),f"Rank #{rank}",font =font_medium ,fill =text_color )


        bar_x ,bar_y =info_x ,160 
        bar_width ,bar_height =480 ,20 

        draw .rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),fill =(30 ,30 ,30 ))

        if needed >0 :
            progress_width =int ((progress /needed )*bar_width )
            if progress_width >0 :
                draw .rectangle ((bar_x ,bar_y ,bar_x +progress_width ,bar_y +bar_height ),fill =text_color )

        xp_text =f"{progress:,} / {needed:,} XP"
        text_bbox =draw .textbbox ((0 ,0 ),xp_text ,font =font_small )
        text_width =text_bbox [2 ]-text_bbox [0 ]
        text_x =bar_x +(bar_width -text_width )//2 
        draw .text ((text_x ,bar_y +2 ),xp_text ,font =font_small ,fill =(220 ,220 ,220 ))


        stats_x =700 
        draw .text ((stats_x ,85 ),f"Messages: {messages:,}",font =font_small ,fill =text_color )
        draw .text ((stats_x ,115 ),f"Total XP: {xp:,}",font =font_small ,fill =text_color )

        percentage =(progress /needed *100 )if needed >0 else 100 
        draw .text ((stats_x ,145 ),f"Progress: {percentage:.1f}%",font =font_small ,fill =text_color )

    @level .command (name ="rank",description ="View your current rank and level")
    async def rank (self ,ctx ,member :Optional [discord .Member ]=None ):
        """Display rank card"""
        member =member or ctx .author 
        guild_id =ctx .guild .id 

        try :
            rank_card =await self .create_rank_card (member ,guild_id )

            if rank_card :
                if isinstance (rank_card ,str ):

                    await ctx .send (rank_card )
                else :

                    file =discord .File (fp =rank_card ,filename ="rank_card.png")
                    await ctx .send (file =file )
                try :
                    rank_card .close ()
                except :
                    pass 
            else :
                pass 
        except Exception as e :
            logger .error (f"Error in rank command: {e}")
            pass 

    @level .command (name ="settings",description ="Configure leveling settings",aliases =['config'])
    @commands .has_permissions (administrator =True )
    async def settings (self ,ctx ):
        """Leveling settings configuration"""
        try :
            current_settings =await self .get_guild_settings (ctx .guild .id )

            interaction =getattr (ctx ,'interaction',None )
            if interaction is not None :
                await interaction .response .send_modal (LevelConfigModal (self ,current_settings ))
                return 

            embed =discord .Embed (
            title ="⚙️ Chat Leveling Settings",
            description ="Press the button below to open the settings popup.\n"
            "Everything is edited in the popup — no message-by-message questions.",
            color =0xFF0000 ,
            timestamp =datetime .now (IST )
            )
            embed .add_field (name ="Current Settings",value =_leveling_summary (current_settings ),inline =False )
            await ctx .send (
            embed =embed ,
            view =SettingsLauncherView (lambda :LevelConfigModal (self ,current_settings ))
            )

        except Exception as e :
            logger .error (f"Error in settings command: {e}")
            pass 

    @level .command (name ="setxp",description ="Set chat XP per message (a number like 20 or a range like 15-25)")
    @commands .has_permissions (administrator =True )
    async def setxp (self ,ctx ,amount :str ):
        """Set chat XP per message, either a fixed number or a range"""
        try :
            parsed_range =parse_xp_range (amount )
            if parsed_range is None :
                await ctx .send (f"{CROSS} Use a number like `20` or a range like `15-25` (each 1-999).")
                return 

            xp_low ,xp_high =parsed_range 
            xp_text =str (xp_low )if xp_low ==xp_high else f"{xp_low}-{xp_high}"

            async with aiosqlite .connect (self .db_path )as db :
                async with db .execute ("SELECT guild_id FROM leveling_settings WHERE guild_id = ?",(ctx .guild .id ,))as cursor :
                    exists =await cursor .fetchone ()

                if exists :
                    await db .execute (
                    "UPDATE leveling_settings SET xp_per_message = ?, min_xp = ?, max_xp = ? WHERE guild_id = ?",
                    (xp_high ,xp_low ,xp_high ,ctx .guild .id ))
                else :
                    await db .execute (
                    "INSERT INTO leveling_settings (guild_id, xp_per_message, min_xp, max_xp) VALUES (?, ?, ?, ?)",
                    (ctx .guild .id ,xp_high ,xp_low ,xp_high ))

                await db .commit ()

            embed =discord .Embed (
            title =f"{TICK} XP Amount Updated",
            description =f"Chat XP per message has been set to **{xp_text} XP**",
            color =0x00FF00 ,
            timestamp =datetime .now (IST )
            )
            await ctx .send (embed =embed )

        except Exception as e :
            logger .error (f"Error setting XP amount: {e}")
            pass 

    @level .command (name ="setmessage",description ="Set level-up message")
    @commands .has_permissions (administrator =True )
    async def setmessage (self ,ctx ,*,message :str ):
        """Set level-up message"""
        try :
            if len (message )>2000 :
                await ctx .send (f"{CROSS} Level-up message must be less than 2000 characters!")
                return 

            async with aiosqlite .connect (self .db_path )as db :
                async with db .execute ("SELECT guild_id FROM leveling_settings WHERE guild_id = ?",(ctx .guild .id ,))as cursor :
                    exists =await cursor .fetchone ()

                if exists :
                    await db .execute ("UPDATE leveling_settings SET level_message = ? WHERE guild_id = ?",(message ,ctx .guild .id ))
                else :
                    await db .execute ("INSERT INTO leveling_settings (guild_id, level_message) VALUES (?, ?)",(ctx .guild .id ,message ))

                await db .commit ()

            embed =discord .Embed (
            title =f"{TICK} Level-Up Message Updated",
            description =f"Level-up message has been set to:\n```{message}```",
            color =0x00FF00 ,
            timestamp =datetime .now (IST )
            )
            await ctx .send (embed =embed )

        except Exception as e :
            logger .error (f"Error setting level message: {e}")
            pass 

    @level .command (name ="setcolor",description ="Set embed color")
    @commands .has_permissions (administrator =True )
    async def setcolor (self ,ctx ,color :str ):
        """Set embed color"""
        try :

            if not color .startswith ('#'):
                color ='#'+color 

            if not validate_hex_color (color ):
                await ctx .send (f"{CROSS} Invalid hex color format! Use format like #FF0000")
                return 

            color_int =hex_to_int (color )

            async with aiosqlite .connect (self .db_path )as db :
                async with db .execute ("SELECT guild_id FROM leveling_settings WHERE guild_id = ?",(ctx .guild .id ,))as cursor :
                    exists =await cursor .fetchone ()

                if exists :
                    await db .execute ("UPDATE leveling_settings SET embed_color = ? WHERE guild_id = ?",(color_int ,ctx .guild .id ))
                else :
                    await db .execute ("INSERT INTO leveling_settings (guild_id, embed_color) VALUES (?, ?)",(ctx .guild .id ,color_int ))

                await db .commit ()

            embed =discord .Embed (
            title =f"{TICK} Embed Color Updated",
            description =f"Embed color has been set to **{color}**",
            color =color_int ,
            timestamp =datetime .now (IST )
            )
            await ctx .send (embed =embed )

        except Exception as e :
            logger .error (f"Error setting embed color: {e}")
            pass 

    @level .command (name ="thumbnail",description ="Toggle user thumbnail in level-up messages")
    @commands .has_permissions (administrator =True )
    async def thumbnail (self ,ctx ,setting :str ):
        """Toggle thumbnail setting"""
        try :
            setting =setting .lower ()
            if setting not in ['on','off','true','false','yes','no','enable','disable']:
                await ctx .send (f"{CROSS} Use: `on/off`, `true/false`, `yes/no`, or `enable/disable`")
                return 

            enabled =setting in ['on','true','yes','enable']

            async with aiosqlite .connect (self .db_path )as db :
                async with db .execute ("SELECT guild_id FROM leveling_settings WHERE guild_id = ?",(ctx .guild .id ,))as cursor :
                    exists =await cursor .fetchone ()

                if exists :
                    await db .execute ("UPDATE leveling_settings SET thumbnail_enabled = ? WHERE guild_id = ?",(1 if enabled else 0 ,ctx .guild .id ))
                else :
                    await db .execute ("INSERT INTO leveling_settings (guild_id, thumbnail_enabled) VALUES (?, ?)",(ctx .guild .id ,1 if enabled else 0 ))

                await db .commit ()

            embed =discord .Embed (
            title =f"{TICK} Thumbnail Setting Updated",
            description =f"User thumbnails in level-up messages: **{'Enabled' if enabled else 'Disabled'}**",
            color =0x00FF00 ,
            timestamp =datetime .now (IST )
            )
            await ctx .send (embed =embed )

        except Exception as e :
            logger .error (f"Error setting thumbnail: {e}")
            pass 

    @level .command (name ="cooldown",description ="Set message cooldown in seconds")
    @commands .has_permissions (administrator =True )
    async def cooldown (self ,ctx ,seconds :int ):
        """Set message cooldown"""
        try :
            if seconds <0 or seconds >3600 :
                await ctx .send (f"{CROSS} Cooldown must be between 0 and 3600 seconds (1 hour)!")
                return 

            async with aiosqlite .connect (self .db_path )as db :
                async with db .execute ("SELECT guild_id FROM leveling_settings WHERE guild_id = ?",(ctx .guild .id ,))as cursor :
                    exists =await cursor .fetchone ()

                if exists :
                    await db .execute ("UPDATE leveling_settings SET cooldown_seconds = ? WHERE guild_id = ?",(seconds ,ctx .guild .id ))
                else :
                    await db .execute ("INSERT INTO leveling_settings (guild_id, cooldown_seconds) VALUES (?, ?)",(ctx .guild .id ,seconds ))

                await db .commit ()

            embed =discord .Embed (
            title =f"{TICK} Cooldown Updated",
            description =f"Message cooldown has been set to **{seconds} seconds**",
            color =0x00FF00 ,
            timestamp =datetime .now (IST )
            )
            await ctx .send (embed =embed )

        except Exception as e :
            logger .error (f"Error setting cooldown: {e}")
            pass 

    @level .group (name ="rewards",invoke_without_command =True ,description ="Manage level rewards")
    async def rewards (self ,ctx ):
        """Level rewards management"""
        if ctx .invoked_subcommand is None :
            await ctx .send_help (ctx .command )

    @rewards .command (name ="add",description ="Add a level reward")
    @commands .has_permissions (administrator =True )
    async def rewards_add (self ,ctx ,level :int ,role :discord .Role ,remove_previous :bool =False ):
        """Add level reward"""
        try :
            if level <=0 :
                await ctx .send ("Level must be greater than 0.")
                return 

            async with aiosqlite .connect ("db/leveling.db")as db :
                await db .execute (
                "INSERT OR REPLACE INTO level_rewards (guild_id, level, role_id, remove_previous) VALUES (?, ?, ?, ?)",
                (ctx .guild .id ,level ,role .id ,int (remove_previous ))
                )
                await db .commit ()

            await ctx .send (f"Added reward {role.mention} for level {level} (Remove Previous: {remove_previous})")
        except Exception as e :
            logger .error (f"Error in rewards add command: {e}")
            pass 

    @rewards .command (name ="remove",description ="Remove a level reward")
    @commands .has_permissions (administrator =True )
    async def rewards_remove (self ,ctx ,level :int ):
        """Remove level reward"""
        try :
            async with aiosqlite .connect ("db/leveling.db")as db :
                await db .execute (
                "DELETE FROM level_rewards WHERE guild_id = ? AND level = ?",
                (ctx .guild .id ,level )
                )
                await db .commit ()

            await ctx .send (f"Removed reward for level {level}")
        except Exception as e :
            logger .error (f"Error in rewards remove command: {e}")
            pass 

    @rewards .command (name ="list",description ="List all level rewards")
    @commands .has_permissions (administrator =True )
    async def rewards_list (self ,ctx ):
        """List level rewards"""
        try :
            async with aiosqlite .connect ("db/leveling.db")as db :
                async with db .execute (
                "SELECT level, role_id, remove_previous FROM level_rewards WHERE guild_id = ? ORDER BY level",
                (ctx .guild .id ,)
                )as cursor :
                    rewards =await cursor .fetchall ()

            if not rewards :
                await ctx .send ("No level rewards configured.")
                return 

            embed =discord .Embed (title ="Level Rewards",color =0xFF0000 ,timestamp =datetime .now (IST ))
            for level ,role_id ,remove_previous in rewards :
                role =ctx .guild .get_role (role_id )
                role_name =role .mention if role else "Role not found"
                embed .add_field (name =f"Level {level}",value =f"Role: {role_name} (Remove Previous: {remove_previous})",inline =False )

            await ctx .send (embed =embed )
        except Exception as e :
            logger .error (f"Error in rewards list command: {e}")
            pass 

    @level .group (name ="multiplier",invoke_without_command =True ,description ="Manage XP multipliers")
    async def multiplier (self ,ctx ):
        """XP multiplier management"""
        if ctx .invoked_subcommand is None :
            await ctx .send_help (ctx .command )

    @multiplier .command (name ="add",description ="Add an XP multiplier")
    @commands .has_permissions (administrator =True )
    async def multiplier_add (self ,ctx ,target_type :str ,target :str ,multiplier :float ):
        """Add XP multiplier"""
        try :
            if target_type not in ["role","channel"]:
                await ctx .send ("Invalid target type. Must be 'role' or 'channel'.")
                return 

            if multiplier <=0 :
                await ctx .send ("Multiplier must be greater than 0.")
                return 

            if target_type =="role":
                try :
                    role_id =int (target )
                    target_id =ctx .guild .get_role (role_id ).id 
                except :
                    await ctx .send ("Invalid role ID.")
                    return 
            else :
                try :
                    channel_id =int (target )
                    target_id =ctx .guild .get_channel (channel_id ).id 
                except :
                    await ctx .send ("Invalid channel ID.")
                    return 

            async with aiosqlite .connect ("db/leveling.db")as db :
                await db .execute (
                "INSERT OR REPLACE INTO xp_multipliers (guild_id, target_id, target_type, multiplier) VALUES (?, ?, ?, ?)",
                (ctx .guild .id ,target_id ,target_type ,multiplier )
                )
                await db .commit ()

            await ctx .send (f"Added {multiplier}x multiplier for {target_type} {target}")
        except Exception as e :
            logger .error (f"Error in multiplier add command: {e}")
            pass 

    @multiplier .command (name ="remove",description ="Remove an XP multiplier")
    @commands .has_permissions (administrator =True )
    async def multiplier_remove (self ,ctx ,target_type :str ,target :str ):
        """Remove XP multiplier"""
        try :
            if target_type not in ["role","channel"]:
                await ctx .send ("Invalid target type. Must be 'role' or 'channel'.")
                return 

            if target_type =="role":
                try :
                    role_id =int (target )
                    target_id =ctx .guild .get_role (role_id ).id 
                except :
                    await ctx .send ("Invalid role ID.")
                    return 
            else :
                try :
                    channel_id =int (target )
                    target_id =ctx .guild .get_channel (channel_id ).id 
                except :
                    await ctx .send ("Invalid channel ID.")
                    return 

            async with aiosqlite .connect ("db/leveling.db")as db :
                await db .execute (
                "DELETE FROM xp_multipliers WHERE guild_id = ? AND target_id = ? AND target_type = ?",
                (ctx .guild .id ,target_id ,target_type )
                )
                await db .commit ()

            await ctx .send (f"Removed multiplier for {target_type} {target}")
        except Exception as e :
            logger .error (f"Error in multiplier remove command: {e}")
            pass 

    @multiplier .command (name ="list",description ="List all XP multipliers")
    @commands .has_permissions (administrator =True )
    async def multiplier_list (self ,ctx ):
        """List XP multipliers"""
        try :
            async with aiosqlite .connect ("db/leveling.db")as db :
                async with db .execute (
                "SELECT target_id, target_type, multiplier FROM xp_multipliers WHERE guild_id = ?",
                (ctx .guild .id ,)
                )as cursor :
                    multipliers =await cursor .fetchall ()

            if not multipliers :
                await ctx .send ("No XP multipliers configured.")
                return 

            embed =discord .Embed (title ="XP Multipliers",color =0xFF0000 ,timestamp =datetime .now (IST ))
            for target_id ,target_type ,multiplier in multipliers :
                if target_type =="role":
                    role =ctx .guild .get_role (target_id )
                    target_name =role .mention if role else "Role not found"
                else :
                    channel =ctx .guild .get_channel (target_id )
                    target_name =channel .mention if channel else "Channel not found"
                embed .add_field (name =f"{target_type.capitalize()}: {target_name}",value =f"Multiplier: {multiplier}x",inline =False )

            await ctx .send (embed =embed )
        except Exception as e :
            logger .error (f"Error in multiplier list command: {e}")
            pass 

    @level .group (name ="blacklist",invoke_without_command =True ,description ="Manage leveling blacklists")
    async def blacklist (self ,ctx ):
        """Leveling blacklist management"""
        if ctx .invoked_subcommand is None :
            await ctx .send_help (ctx .command )

    @blacklist .command (name ="add",description ="Add to the leveling blacklist")
    @commands .has_permissions (administrator =True )
    async def blacklist_add (self ,ctx ,target_type :str ,target :str ):
        """Add to leveling blacklist"""
        try :
            if target_type not in ["role","channel"]:
                await ctx .send ("Invalid target type. Must be 'role' or 'channel'.")
                return 

            if target_type =="role":
                try :
                    role_id =int (target )
                    target_id =ctx .guild .get_role (role_id ).id 
                except :
                    await ctx .send ("Invalid role ID.")
                    return 
            else :
                try :
                    channel_id =int (target )
                    target_id =ctx .guild .get_channel (channel_id ).id 
                except :
                    await ctx .send ("Invalid channel ID.")
                    return 

            async with aiosqlite .connect ("db/leveling.db")as db :
                await db .execute (
                "INSERT OR REPLACE INTO leveling_blacklist (guild_id, target_id, target_type) VALUES (?, ?, ?)",
                (ctx .guild .id ,target_id ,target_type )
                )
                await db .commit ()

            await ctx .send (f"Added {target_type} {target} to the leveling blacklist.")
        except Exception as e :
            logger .error (f"Error in blacklist add command: {e}")
            pass 

    @blacklist .command (name ="remove",description ="Remove from the leveling blacklist")
    @commands .has_permissions (administrator =True )
    async def blacklist_remove (self ,ctx ,target_type :str ,target :str ):
        """Remove from leveling blacklist"""
        try :
            if target_type not in ["role","channel"]:
                await ctx .send ("Invalid target type. Must be 'role' or 'channel'.")
                return 

            if target_type =="role":
                try :
                    role_id =int (target )
                    target_id =ctx .guild .get_role (role_id ).id 
                except :
                    await ctx .send ("Invalid role ID.")
                    return 
            else :
                try :
                    channel_id =int (target )
                    target_id =ctx .guild .get_channel (channel_id ).id 
                except :
                    await ctx .send ("Invalid channel ID.")
                    return 

            async with aiosqlite .connect ("db/leveling.db")as db :
                await db .execute (
                "DELETE FROM leveling_blacklist WHERE guild_id = ? AND target_id = ? AND target_type = ?",
                (ctx .guild .id ,target_id ,target_type )
                )
                await db .commit ()

            await ctx .send (f"Removed {target_type} {target} from the leveling blacklist.")
        except Exception as e :
            logger .error (f"Error in blacklist remove command: {e}")
            pass 

    @blacklist .command (name ="list",description ="List the leveling blacklist")
    @commands .has_permissions (administrator =True )
    async def blacklist_list (self ,ctx ):
        """List leveling blacklist"""
        try :
            async with aiosqlite .connect ("db/leveling.db")as db :
                async with db .execute (
                "SELECT target_id, target_type FROM leveling_blacklist WHERE guild_id = ?",
                (ctx .guild .id ,)
                )as cursor :
                    blacklisted =await cursor .fetchall ()

            if not blacklisted :
                await ctx .send ("The leveling blacklist is empty.")
                return 

            embed =discord .Embed (title ="Leveling Blacklist",color =0xFF0000 ,timestamp =datetime .now (IST ))
            for target_id ,target_type in blacklisted :
                if target_type =="role":
                    role =ctx .guild .get_role (target_id )
                    target_name =role .mention if role else "Role not found"
                else :
                    channel =ctx .guild .get_channel (target_id )
                    target_name =channel .mention if channel else "Channel not found"
                embed .add_field (name =f"{target_type.capitalize()}: {target_name}",value ="",inline =False )

            await ctx .send (embed =embed )
        except Exception as e :
            logger .error (f"Error in blacklist list command: {e}")
            pass 

    async def apply_level_roles(self, guild, member, level):
        """Apply level-based roles to a member. Returns the roles added."""
        granted = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?", (guild.id, level)) as cursor:
                    result = await cursor.fetchone()
                    if result:
                        role_id = result[0]
                        role = guild.get_role(role_id)
                        if role and role not in member.roles:
                            try:
                                await member.add_roles(role, reason="Reached level {}".format(level))
                                granted.append(role)
                                logger.info(f"Applied level role {role.name} to {member.name} in {guild.name}")
                            except discord.Forbidden:
                                logger.error(f"Missing permissions to add role {role.name} to {member.name} in {guild.name}")
                            except discord.HTTPException as e:
                                logger.error(f"Failed to add role {role.name} to {member.name} in {guild.name}: {e}")
                        elif role:
                            logger.info(f"{member.name} already has level role {role.name} in {guild.name}")
                        else:
                            logger.warning(f"Role with ID {role_id} not found in {guild.name}")
        except Exception as e:
            logger.error(f"Error applying level roles: {e}")
        return granted

    @commands .hybrid_command (name ="setlevelrole",description ="Set a role for a specific level (admin only)")
    @commands .has_permissions (administrator =True )
    async def set_level_role (self ,ctx ,level :int ,role :discord .Role ):
        """Set a level role."""
        try :
            if level <=0 :
                await ctx .send ("Level must be greater than 0.")
                return 

            async with aiosqlite .connect (self .db_path )as db :
                await db .execute ("INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)",(ctx .guild .id ,level ,role .id ))
                await db .commit ()

            await ctx .send (f"Set role {role.mention} for level {level}.")
        except Exception as e :
            logger .error (f"Error setting level role: {e}")
            pass 

    @commands .hybrid_command (name ="removelevelrole",description ="Remove a level role (admin only)")
    @commands .has_permissions (administrator =True )
    async def remove_level_role (self ,ctx ,level :int ):
        """Remove a level role."""
        try :
            async with aiosqlite .connect (self .db_path )as db :
                await db .execute ("DELETE FROM level_roles WHERE guild_id = ? AND level = ?",(ctx .guild .id ,level ))
                await db .commit ()

            await ctx .send (f"Removed role for level {level}.")
        except Exception as e :
            logger .error (f"Error removing level role: {e}")
            pass 

    @commands .hybrid_command (name ="listlevelroles",description ="List all level roles (admin only)")
    @commands .has_permissions (administrator =True )
    async def list_level_roles (self ,ctx ):
        """List all level roles."""
        try :
            async with aiosqlite .connect (self .db_path )as db :
                async with db .execute ("SELECT level, role_id FROM level_roles WHERE guild_id = ?",(ctx .guild .id ,))as cursor :
                    roles =await cursor .fetchall ()

            if not roles :
                await ctx .send ("No level roles set for this server.")
                return 

            embed =discord .Embed (title ="Level Roles",color =0xFF0000 ,timestamp =datetime .now (IST ))
            for level ,role_id in roles :
                role =ctx .guild .get_role (role_id )
                role_name =role .mention if role else "Role not found"
                embed .add_field (name =f"Level {level}",value =f"Role: {role_name}",inline =False )

            await ctx .send (embed =embed )
        except Exception as e :
            logger .error (f"Error listing level roles: {e}")
            pass 

    @commands .hybrid_command (name ="resetxp",description ="Reset a user's XP (admin only)")
    @commands .has_permissions (administrator =True )
    async def reset_xp (self ,ctx ,member :discord .Member ):
        """Reset a user's XP and level to default values."""
        try :
            async with aiosqlite .connect (self .db_path )as db :
                await db .execute ("UPDATE users SET xp = 0, level = 1 WHERE guild_id = ? AND user_id = ?",(ctx .guild .id ,member .id ))
                await db .commit ()

            await ctx .send (f"Successfully reset XP for {member.mention}.")
        except Exception as e :
            logger .error (f"Error resetting XP: {e}")
            pass 

    @commands .hybrid_command (name ="setxp",description ="Set a user's XP (admin only)")
    @commands .has_permissions (administrator =True )
    async def set_xp (self ,ctx ,member :discord .Member ,xp :int ):
        """Set a user's XP to a specific value."""
        try :
            level =calculate_level_from_xp (xp )
            async with aiosqlite .connect (self .db_path )as db :
                await db .execute ("UPDATE users SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?",(xp ,level ,ctx .guild .id ,member .id ))
                await db .commit ()

            await ctx .send (f"Successfully set XP for {member.mention} to {xp:,}.")
        except Exception as e :
            logger .error (f"Error setting XP: {e}")
            pass 

    @commands .hybrid_command (name ="setlevel",description ="Set a user's level (admin only)")
    @commands .has_permissions (administrator =True )
    async def set_level (self ,ctx ,member :discord .Member ,level :int ):
        """Set a user's level to a specific value."""
        try :
            xp =calculate_xp_for_level (level )
            async with aiosqlite .connect (self .db_path )as db :
                await db .execute ("UPDATE users SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?",(xp ,level ,ctx .guild .id ,member .id ))
                await db .commit ()

            await ctx .send (f"Successfully set level for {member.mention} to {level:,}.")
        except Exception as e :
            logger .error (f"Error setting level: {e}")
            pass 

    @level .command (name ="leaderboard",description ="View the server level leaderboard")
    @commands .cooldown (1 ,10 ,commands .BucketType .guild )
    async def level_leaderboard (self ,ctx ):
        """Display server level leaderboard"""
        try :
            if isinstance (ctx ,discord .Interaction ):
                await ctx .response .defer ()

            async with aiosqlite .connect ("db/leveling.db")as db :

                cursor =await db .execute ('''
                    SELECT user_id, xp, messages FROM user_xp 
                    WHERE guild_id = ? 
                    ORDER BY xp DESC 
                    LIMIT 10
                ''',(ctx .guild .id ,))

                top_users =await cursor .fetchall ()

            if not top_users :
                embed =discord .Embed (
                title ="📊 Server Level Leaderboard",
                description ="No users found in the leaderboard yet!",
                color =0xFF0000 
                )
                if isinstance (ctx ,discord .Interaction ):
                    await ctx .followup .send (embed =embed )
                else :
                    await ctx .send (embed =embed )
                return 


            leaderboard_image =await self .create_leaderboard_image (ctx .guild ,top_users )

            if leaderboard_image :
                if isinstance (leaderboard_image ,str ):

                    if isinstance (ctx ,discord .Interaction ):
                        await ctx .followup .send (leaderboard_image )
                    else :
                        await ctx .send (leaderboard_image )
                else :

                    file =discord .File (fp =leaderboard_image ,filename ="level_leaderboard.png")
                    if isinstance (ctx ,discord .Interaction ):
                        await ctx .followup .send (file =file )
                    else :
                        await ctx .send (file =file )
                    try :
                        leaderboard_image .close ()
                    except :
                        pass 
            else :
                if isinstance (ctx ,discord .Interaction ):
                    await ctx .followup .send ("Failed to generate leaderboard.")
                else :
                    pass 

        except Exception as e :
            logger .error (f"Error in level leaderboard command: {e}")
            error_msg =f"An error occurred: {e}"
            if isinstance (ctx ,discord .Interaction ):
                await ctx .followup .send (error_msg )
            else :
                await ctx .send (error_msg )

    async def create_leaderboard_image (self ,guild ,top_users ):
        """Create enhanced visual leaderboard image with custom background support and modern design"""
        try :
            if not PIL_AVAILABLE :
                return self .create_text_leaderboard (guild ,top_users )


            width ,height =1920 ,1080 


            background_loaded =False 
            background_extensions =['.jpg','.jpeg','.png','.gif','.webp']

            for ext in background_extensions :
                try :
                    bg_path =f"/home/container/assets/leaderboardlevel{ext}"
                    if os .path .exists (bg_path ):
                        temp_bg =Image .open (bg_path )
                        bg_width ,bg_height =temp_bg .size 


                        ratio =bg_width /bg_height 

                        if 1.7 <=ratio <=1.8 :
                            width ,height =1920 ,1080 
                        elif 1.3 <=ratio <=1.35 :
                            width ,height =1600 ,1200 
                        elif 0.95 <=ratio <=1.05 :
                            width ,height =1200 ,1200 
                        elif 0.7 <=ratio <=0.85 :
                            width ,height =1200 ,1600 
                        else :

                            if bg_width >2000 or bg_height >1500 :
                                scale =min (2000 /bg_width ,1500 /bg_height )
                                width =int (bg_width *scale )
                                height =int (bg_height *scale )
                            else :
                                width ,height =bg_width ,bg_height 

                        temp_bg .close ()
                        break 
                except Exception as e :
                    logger .error (f"Failed to analyze background {bg_path}: {e}")
                    continue 


            for ext in background_extensions :
                try :
                    bg_path =f"/home/container/assets/leaderboardlevel{ext}"
                    if os .path .exists (bg_path ):
                        background_img =Image .open (bg_path )

                        if hasattr (background_img ,'is_animated')and background_img .is_animated :
                            background_img =background_img .convert ('RGBA')

                        background_img =background_img .resize ((width ,height ),Image .Resampling .LANCZOS )
                        img =background_img .convert ('RGB')
                        background_loaded =True 
                        logger .info (f"Loaded custom background: {bg_path} - Resized to {width}x{height}")
                        break 
                except Exception as e :
                    logger .error (f"Failed to load background {bg_path}: {e}")
                    continue 


            if not background_loaded :
                img =Image .new ('RGB',(width ,height ),(15 ,15 ,25 ))
                draw_temp =ImageDraw .Draw (img )

                for y in range (height ):
                    factor =y /height 
                    r =int (15 +(45 -15 )*factor +10 *math .sin (factor *math .pi *2 ))
                    g =int (15 +(55 -15 )*factor +15 *math .sin (factor *math .pi *3 ))
                    b =int (25 +(85 -25 )*factor +20 *math .sin (factor *math .pi *4 ))
                    draw_temp .line ([(0 ,y ),(width ,y )],fill =(min (255 ,max (0 ,r )),min (255 ,max (0 ,g )),min (255 ,max (0 ,b ))))

            draw =ImageDraw .Draw (img )


            try :
                title_font =ImageFont .truetype ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",54 )
                name_font =ImageFont .truetype ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",32 )
                stats_font =ImageFont .truetype ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",22 )
                rank_font =ImageFont .truetype ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",40 )
                small_font =ImageFont .truetype ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",19 )
            except (OSError ,IOError ):
                title_font =ImageFont .load_default ()
                name_font =ImageFont .load_default ()
                stats_font =ImageFont .load_default ()
                rank_font =ImageFont .load_default ()
                small_font =ImageFont .load_default ()


            title =f"🏆 {guild.name} Level Leaderboard"
            title_bbox =draw .textbbox ((0 ,0 ),title ,font =title_font )
            title_width =title_bbox [2 ]-title_bbox [0 ]
            title_x =(width -title_width )//2 


            title_bg_margin =50 
            title_y =25 
            title_height =90 


            draw .rounded_rectangle (
            (title_x -title_bg_margin ,title_y ,title_x +title_width +title_bg_margin ,title_y +title_height ),
            radius =25 ,fill =(0 ,0 ,0 ,160 )
            )
            draw .rounded_rectangle (
            (title_x -title_bg_margin ,title_y ,title_x +title_width +title_bg_margin ,title_y +title_height ),
            radius =25 ,outline =(255 ,215 ,0 ,200 ),width =3 
            )


            for offset in [(5 ,5 ),(4 ,4 ),(3 ,3 ),(2 ,2 ),(1 ,1 )]:
                alpha =100 -(offset [0 ]*15 )
                draw .text ((title_x +offset [0 ],title_y +20 +offset [1 ]),title ,font =title_font ,fill =(0 ,0 ,0 ,alpha ))
            draw .text ((title_x ,title_y +20 ),title ,font =title_font ,fill =(255 ,215 ,0 ))


            start_y =180 
            entry_height =120 
            margin_left =100 
            margin_right =100 

            for i ,(user_id ,xp ,messages )in enumerate (top_users ):
                user =guild .get_member (user_id )
                if not user :
                    continue 

                y =start_y +(i *entry_height )
                level =calculate_level_from_xp (xp )


                if i ==0 :
                    rank_color =(255 ,215 ,0 )
                    bg_color =(40 ,35 ,15 )
                    border_color =(255 ,215 ,0 )
                    accent_color =(255 ,235 ,100 )
                elif i ==1 :
                    rank_color =(192 ,192 ,192 )
                    bg_color =(35 ,35 ,40 )
                    border_color =(192 ,192 ,192 )
                    accent_color =(220 ,220 ,220 )
                elif i ==2 :
                    rank_color =(205 ,127 ,50 )
                    bg_color =(40 ,30 ,20 )
                    border_color =(205 ,127 ,50 )
                    accent_color =(230 ,150 ,80 )
                else :
                    rank_color =(120 ,180 ,255 )
                    bg_color =(25 ,30 ,40 )
                    border_color =(80 ,120 ,160 )
                    accent_color =(150 ,200 ,255 )


                entry_bg_y =y -15 
                entry_bg_height =entry_height -10 


                draw .rounded_rectangle (
                (margin_left ,entry_bg_y ,width -margin_right ,entry_bg_y +entry_bg_height ),
                radius =20 ,fill =(0 ,0 ,0 ,180 )
                )


                for border_layer in range (4 ):
                    border_alpha =180 -(border_layer *30 )
                    draw .rounded_rectangle (
                    (margin_left -border_layer ,entry_bg_y -border_layer ,
                    width -margin_right +border_layer ,entry_bg_y +entry_bg_height +border_layer ),
                    radius =20 +border_layer ,outline =(*border_color ,border_alpha ),width =2 
                    )


                rank_x =margin_left +40 
                rank_text =f"#{i + 1}"


                rank_circle_size =55 
                rank_circle_y =y +20 
                draw .ellipse (
                (rank_x -5 ,rank_circle_y ,rank_x +rank_circle_size ,rank_circle_y +rank_circle_size ),
                fill =(*rank_color ,60 )
                )
                draw .ellipse (
                (rank_x -5 ,rank_circle_y ,rank_x +rank_circle_size ,rank_circle_y +rank_circle_size ),
                outline =rank_color ,width =3 
                )


                rank_bbox =draw .textbbox ((0 ,0 ),rank_text ,font =rank_font )
                rank_text_width =rank_bbox [2 ]-rank_bbox [0 ]
                rank_text_height =rank_bbox [3 ]-rank_bbox [1 ]
                rank_text_x =rank_x +(rank_circle_size -rank_text_width )//2 -5 
                rank_text_y =rank_circle_y +(rank_circle_size -rank_text_height )//2 


                draw .text ((rank_text_x +3 ,rank_text_y +3 ),rank_text ,font =rank_font ,fill =(0 ,0 ,0 ,200 ))
                draw .text ((rank_text_x ,rank_text_y ),rank_text ,font =rank_font ,fill =rank_color )


                avatar_x =margin_left +140 
                avatar_y =y +20 
                avatar_size =70 


                for border_layer in range (3 ):
                    border_size =avatar_size +(border_layer *6 )
                    border_x =avatar_x -(border_layer *3 )
                    border_y =avatar_y -(border_layer *3 )
                    alpha =200 -(border_layer *40 )

                    draw .ellipse (
                    (border_x ,border_y ,border_x +border_size ,border_y +border_size ),
                    outline =(*rank_color ,alpha ),width =3 
                    )


                try :
                    avatar_url =str (user .display_avatar .with_size (512 ).url )
                    response =requests .get (avatar_url ,timeout =10 )
                    if response .status_code ==200 :
                        avatar_img =Image .open (io .BytesIO (response .content ))
                        avatar_img =avatar_img .resize ((avatar_size ,avatar_size ),Image .Resampling .LANCZOS )


                        mask =Image .new ('L',(avatar_size ,avatar_size ),0 )
                        mask_draw =ImageDraw .Draw (mask )
                        mask_draw .ellipse ((0 ,0 ,avatar_size ,avatar_size ),fill =255 )


                        avatar_img .putalpha (mask )
                        img .paste (avatar_img ,(avatar_x ,avatar_y ),avatar_img )
                    else :
                        raise Exception ("Failed to download avatar")
                except Exception as e :

                    draw .ellipse ((avatar_x ,avatar_y ,avatar_x +avatar_size ,avatar_y +avatar_size ),
                    fill =(40 ,40 ,50 ))


                    emoji ="👤"
                    emoji_bbox =draw .textbbox ((0 ,0 ),emoji ,font =name_font )
                    emoji_width =emoji_bbox [2 ]-emoji_bbox [0 ]
                    emoji_height =emoji_bbox [3 ]-emoji_bbox [1 ]
                    emoji_x =avatar_x +(avatar_size -emoji_width )//2 
                    emoji_y =avatar_y +(avatar_size -emoji_height )//2 
                    draw .text ((emoji_x ,emoji_y ),emoji ,font =name_font ,fill =accent_color )


                info_x =margin_left +240 
                username =user .display_name [:18 ]


                username_y =y +15 
                for shadow in [(4 ,4 ),(3 ,3 ),(2 ,2 ),(1 ,1 )]:
                    draw .text ((info_x +shadow [0 ],username_y +shadow [1 ]),username ,font =name_font ,fill =(0 ,0 ,0 ,150 ))
                draw .text ((info_x ,username_y ),username ,font =name_font ,fill =(255 ,255 ,255 ))


                level_text =f"Level {level:,}"
                level_badge_x =info_x 
                level_badge_y =y +55 
                level_bbox =draw .textbbox ((0 ,0 ),level_text ,font =stats_font )
                level_width =level_bbox [2 ]-level_bbox [0 ]


                draw .rounded_rectangle (
                (level_badge_x -8 ,level_badge_y -5 ,level_badge_x +level_width +16 ,level_badge_y +25 ),
                radius =12 ,fill =(*rank_color ,70 )
                )
                draw .rounded_rectangle (
                (level_badge_x -8 ,level_badge_y -5 ,level_badge_x +level_width +16 ,level_badge_y +25 ),
                radius =12 ,outline =rank_color ,width =2 
                )
                draw .text ((level_badge_x ,level_badge_y ),level_text ,font =stats_font ,fill =(255 ,255 ,255 ))


                info_spacing =30 
                xp_text =f"💎 {format_number(xp)} XP"
                msg_text =f"💬 {format_number(messages or 0)} msgs"

                xp_x =info_x +level_width +info_spacing 
                msg_x =xp_x +140 


                stats_bg_y =level_badge_y -2 
                stats_bg_height =24 
                draw .rounded_rectangle (
                (xp_x -5 ,stats_bg_y ,msg_x +150 ,stats_bg_y +stats_bg_height ),
                radius =8 ,fill =(0 ,0 ,0 ,100 )
                )

                draw .text ((xp_x ,level_badge_y ),xp_text ,font =stats_font ,fill =(200 ,220 ,255 ))
                draw .text ((msg_x ,level_badge_y ),msg_text ,font =stats_font ,fill =(255 ,200 ,150 ))


                bar_x =width -margin_right -380 
                bar_y =y +25 
                bar_width =320 
                bar_height =28 


                draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),
                radius =14 ,fill =(20 ,20 ,30 ,200 ))
                draw .rounded_rectangle ((bar_x ,bar_y ,bar_x +bar_width ,bar_y +bar_height ),
                radius =14 ,outline =(80 ,80 ,100 ),width =2 )


                current_level ,progress ,needed =get_level_progress (xp )
                if needed >0 :
                    progress_width =int ((progress /needed )*(bar_width -6 ))
                    if progress_width >0 :

                        for px in range (progress_width ):
                            factor =px /progress_width if progress_width >0 else 0 


                            base_color =rank_color 
                            brightness =0.4 +0.6 *factor 

                            fill_r =min (255 ,int (base_color [0 ]*brightness ))
                            fill_g =min (255 ,int (base_color [1 ]*brightness ))
                            fill_b =min (255 ,int (base_color [2 ]*brightness ))

                            draw .line ([(bar_x +3 +px ,bar_y +3 ),(bar_x +3 +px ,bar_y +bar_height -3 )],
                            fill =(fill_r ,fill_g ,fill_b ))


                        draw .rounded_rectangle (
                        (bar_x +2 ,bar_y +2 ,bar_x +3 +progress_width ,bar_y +bar_height -2 ),
                        radius =12 ,outline =rank_color ,width =2 
                        )


                percentage =(progress /needed *100 )if needed >0 else 100 
                progress_text =f"{percentage:.1f}% to Level {level + 1}"
                progress_bbox =draw .textbbox ((0 ,0 ),progress_text ,font =small_font )
                progress_text_width =progress_bbox [2 ]-progress_bbox [0 ]
                progress_text_x =bar_x +(bar_width -progress_text_width )//2 


                text_bg_y =bar_y +bar_height +8 
                draw .rounded_rectangle (
                (progress_text_x -12 ,text_bg_y -2 ,progress_text_x +progress_text_width +12 ,text_bg_y +18 ),
                radius =8 ,fill =(0 ,0 ,0 ,180 )
                )
                draw .text ((progress_text_x ,text_bg_y ),progress_text ,font =small_font ,fill =(255 ,255 ,255 ))


                xp_progress_text =f"{format_number(progress)} / {format_number(needed)} XP"
                xp_text_bbox =draw .textbbox ((0 ,0 ),xp_progress_text ,font =small_font )
                xp_text_width =xp_text_bbox [2 ]-xp_text_bbox [0 ]
                xp_text_x =bar_x +(bar_width -xp_text_width )//2 

                draw .text ((xp_text_x ,bar_y +6 ),xp_progress_text ,font =small_font ,fill =(200 ,200 ,200 ))


            footer_y =height -80 
            footer_bg_height =50 


            draw .rounded_rectangle (
            (60 ,footer_y ,width -60 ,footer_y +footer_bg_height ),
            radius =15 ,fill =(0 ,0 ,0 ,150 )
            )
            draw .rounded_rectangle (
            (60 ,footer_y ,width -60 ,footer_y +footer_bg_height ),
            radius =15 ,outline =(100 ,100 ,120 ),width =2 
            )

            footer_text =f"✨ Generated at {datetime.now(IST).strftime('%I:%M %p IST')} • {len(top_users)} Active Members • {guild.name}"
            footer_bbox =draw .textbbox ((0 ,0 ),footer_text ,font =small_font )
            footer_width =footer_bbox [2 ]-footer_bbox [0 ]
            footer_x =(width -footer_width )//2 


            draw .text ((footer_x +2 ,footer_y +17 ),footer_text ,font =small_font ,fill =(0 ,0 ,0 ,200 ))
            draw .text ((footer_x ,footer_y +15 ),footer_text ,font =small_font ,fill =(220 ,220 ,240 ))


            img_bytes =io .BytesIO ()
            img .save (img_bytes ,format ='PNG')
            img_bytes .seek (0 )
            img .close ()
            return img_bytes 

        except Exception as e :
            logger .error (f"Error creating leaderboard image: {e}")
            return self .create_text_leaderboard (guild ,top_users )

    def create_text_leaderboard (self ,guild ,top_users ):
        """Create text-based leaderboard when image creation fails"""
        try :
            leaderboard_text =f"🏆 **{guild.name} Level Leaderboard** 🏆\n\n"

            for i ,(user_id ,xp ,messages )in enumerate (top_users ):
                user =guild .get_member (user_id )
                if not user :
                    continue 

                level =calculate_level_from_xp (xp )

                if i ==0 :
                    emoji ="🥇"
                elif i ==1 :
                    emoji ="🥈"
                elif i ==2 :
                    emoji ="🥉"
                else :
                    emoji =f"#{i + 1}"

                leaderboard_text +=f"{emoji} **{user.display_name}**\n"
                leaderboard_text +=f"    Level {level:,} • {format_number(xp)} XP • {format_number(messages or 0)} messages\n\n"

            return leaderboard_text 

        except Exception as e :
            logger .error (f"Error creating text leaderboard: {e}")
            return "Failed to generate leaderboard."

    @level .command (name ="placeholders",description ="Show available placeholders for level-up messages")
    async def placeholders (self ,ctx ):
        """Show placeholders for level-up messages"""
        embed =discord .Embed (
        title ="📝 Available Placeholders",
        description =(
        "**You can use these placeholders in your level-up message:**\n\n"
        "`{user}` / `{user_name}` / `{server_name}` / `{channel}` / `{date}` … — every shared variable works\n"
        "`{level}` - The new level reached\n"
        "`{earned:...}` - Only when a level reward role is earned; `(role)` becomes the role mention\n"
        "`{embed:name}` / `{cv2:name}` - Send a saved embed or Components V2 layout\n\n"
        "**Example:**\n"
        "`Congratulations {user}! You've reached level {level} in {server}!`"
        ),
        color =0x00BFFF ,
        timestamp =datetime .now (IST )
        )
        await ctx .send (embed =embed )

    @level .command (name ="enable",description ="Enable the leveling system")
    @commands .has_permissions (administrator =True )
    async def enable (self ,ctx ):
        try :
            async with aiosqlite .connect (self .db_path )as db :

                async with db .execute ("SELECT enabled FROM leveling_settings WHERE guild_id = ?",(ctx .guild .id ,))as cursor :
                    result =await cursor .fetchone ()

                if result :
                    if result [0 ]==1 :
                        await ctx .send (f"{ZWARNING} Leveling system is already enabled!")
                        return 

                    await db .execute ("UPDATE leveling_settings SET enabled = 1 WHERE guild_id = ?",(ctx .guild .id ,))
                else :

                    await db .execute ("INSERT INTO leveling_settings (guild_id, enabled) VALUES (?, 1)",(ctx .guild .id ,))

                await db .commit ()

            embed =discord .Embed (
            title =f"{TICK} Leveling System Enabled",
            description ="The leveling system has been successfully enabled for this server!\n\n"
            "**Next Steps:**\n"
            "• Use `/chatlevel settings` to configure XP rates and messages\n"
            "• Use `/chatlevel channel` to set level-up announcement channel\n"
            "• Use `/chatlevel rewards add` to set up level rewards",
            color =0x00FF00 ,
            timestamp =datetime .now (IST )
            )
            await ctx .send (embed =embed )

        except Exception as e :
            logger .error (f"Error enabling leveling system: {e}")
            pass 

    @level .command (name ="disable",description ="Disable the leveling system")
    @commands .has_permissions (administrator =True )
    async def disable (self ,ctx ):
        try :
            async with aiosqlite .connect (self .db_path )as db :

                async with db .execute ("SELECT enabled FROM leveling_settings WHERE guild_id = ?",(ctx .guild .id ,))as cursor :
                    result =await cursor .fetchone ()

                if not result :
                    await ctx .send (f"{ZWARNING} Leveling system is not configured for this server!")
                    return 

                if result [0 ]==0 :
                    await ctx .send (f"{ZWARNING} Leveling system is already disabled!")
                    return 

                await db .execute ("UPDATE leveling_settings SET enabled = 0 WHERE guild_id = ?",(ctx .guild .id ,))
                await db .commit ()

            embed =discord .Embed (
            title =f"{CROSS} Leveling System Disabled",
            description ="The leveling system has been disabled for this server.\n\n"
            "**What this means:**\n"
            "• Users will no longer gain XP from messages\n"
            "• Level-up notifications will stop\n"
            "• Existing user data is preserved\n"
            "• Use `/level enable` to re-enable anytime",
            color =0xFF0000 ,
            timestamp =datetime .now (IST )
            )
            await ctx .send (embed =embed )

        except Exception as e :
            logger .error (f"Error disabling leveling system: {e}")
            pass 

    @level .command (name ="stats",description ="View detailed level statistics")
    async def stats (self ,ctx ,member :Optional [discord .Member ]=None ):
        """Display detailed user level statistics with rank card"""
        member =member or ctx .author 
        guild_id =ctx .guild .id 

        try :

            xp ,level ,messages =await self .get_user_data (guild_id ,member .id )
            rank =await self .get_user_rank (guild_id ,member .id )


            current_level ,progress ,needed =get_level_progress (xp )
            next_level =level +1 
            percentage =(progress /needed *100 )if needed >0 else 100 


            async with aiosqlite .connect ("db/leveling.db")as db :
                async with db .execute (
                "SELECT COUNT(*) FROM user_xp WHERE guild_id = ? AND xp > 0",
                (guild_id ,)
                )as cursor :
                    total_members =(await cursor .fetchone ())[0 ]


            avg_xp_per_message =(xp /messages )if messages >0 else 0 
            xp_to_next_level =needed -progress 


            embed =discord .Embed (
            title =f"📊 Level Statistics for {member.display_name}",
            color =0xFF0000 ,
            timestamp =datetime .now (IST )
            )


            embed .add_field (
            name ="🎯 Basic Stats",
            value =f"**Level:** {level:,}\n"
            f"**Total XP:** {format_number(xp)}\n"
            f"**Server Rank:** #{rank:,} / {total_members:,}\n"
            f"**Messages Sent:** {format_number(messages)}",
            inline =True 
            )


            embed .add_field (
            name ="📈 Progress to Level {next_level}",
            value =f"**Current Progress:** {format_number(progress)} / {format_number(needed)} XP\n"
            f"**Percentage:** {percentage:.1f}%\n"
            f"**XP Needed:** {format_number(xp_to_next_level)}\n"
            f"**Progress Bar:** {get_progress_bar(progress, needed, 15)}",
            inline =True 
            )


            embed .add_field (
            name ="📊 Additional Stats",
            value =f"**Avg XP/Message:** {avg_xp_per_message:.1f}\n"
            f"**XP for Level {level}:** {format_number(calculate_xp_for_level(level))}\n"
            f"**XP for Level {next_level}:** {format_number(calculate_xp_for_level(next_level))}\n"
            f"**Total Levels Gained:** {level - 1:,}",
            inline =True 
            )


            percentile =((total_members -rank +1 )/total_members *100 )if total_members >0 else 0 


            if rank ==1 :
                tier ="🏆 Champion"
                tier_color =0xFFD700 
            elif rank <=3 :
                tier ="🥇 Elite"
                tier_color =0xC0C0C0 
            elif rank <=10 :
                tier ="⭐ Expert"
                tier_color =0xCD7F32 
            elif percentile >=90 :
                tier ="💎 Advanced"
                tier_color =0x00FFFF 
            elif percentile >=70 :
                tier ="🔥 Experienced"
                tier_color =0xFF4500 
            elif percentile >=50 :
                tier ="⚡ Intermediate"
                tier_color =0xFFFF00 
            elif percentile >=25 :
                tier ="🌟 Beginner"
                tier_color =0x90EE90 
            else :
                tier ="🌱 Newcomer"
                tier_color =0x98FB98 

            embed .add_field (
            name ="🏅 Rank Information",
            value =f"**Tier:** {tier}\n"
            f"**Percentile:** Top {100-percentile:.1f}%\n"
            f"**Users Below:** {total_members - rank:,}\n"
            f"**Users Above:** {rank - 1:,}",
            inline =False 
            )


            embed .color =tier_color 


            embed .set_thumbnail (url =member .display_avatar .url )


            embed .set_footer (
            text =f"Requested by {ctx.author.display_name} • {ctx.guild.name}",
            icon_url =ctx .author .display_avatar .url 
            )


            rank_card =await self .create_rank_card (member ,guild_id )

            if rank_card and not isinstance (rank_card ,str ):

                file =discord .File (fp =rank_card ,filename ="rank_card.png")
                embed .set_image (url ="attachment://rank_card.png")
                await ctx .send (embed =embed ,file =file )
                try :
                    rank_card .close ()
                except :
                    pass 
            else :

                await ctx .send (embed =embed )
                if isinstance (rank_card ,str ):

                    await ctx .send (f"```{rank_card}```")

        except Exception as e :
            logger .error (f"Error in level stats command: {e}")
            pass 

    @level .command (name ="channel",description ="Set the level-up announcement channel")
    @commands .has_permissions (administrator =True )
    async def channel (self ,ctx ,channel :discord .TextChannel ):
        try :
            async with aiosqlite .connect (self .db_path )as db :

                async with db .execute ("SELECT guild_id FROM leveling_settings WHERE guild_id = ?",(ctx .guild .id ,))as cursor :
                    result =await cursor .fetchone ()

                if result :
                    await db .execute ("UPDATE leveling_settings SET channel_id = ? WHERE guild_id = ?",(channel .id ,ctx .guild .id ))
                else :
                    await db .execute ("INSERT INTO leveling_settings (guild_id, channel_id) VALUES (?, ?)",(ctx .guild .id ,channel .id ))

                await db .commit ()

            embed =discord .Embed (
            title ="📢 Level-Up Channel Set",
            description =f"Level-up messages will now be sent in {channel.mention}\n\n"
            "**Note:** Make sure the bot has permission to send messages in this channel!",
            color =0x00BFFF ,
            timestamp =datetime .now (IST )
            )
            await ctx .send (embed =embed )

        except Exception as e :
            logger .error (f"Error setting level channel: {e}")
            pass

    # ── Voice levels ──────────────────────────────────────────────────────

    async def get_vc_settings(self, guild_id):
        """Voice leveling settings, kept separate from the chat settings."""
        defaults = {
            'enabled': True,
            'channel_id': None,
            'level_message': DEFAULT_VC_MESSAGE,
            'min_xp': 10,
            'max_xp': 20,
        }
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT * FROM vc_settings WHERE guild_id = ?", (guild_id,)
                ) as cursor:
                    row = await cursor.fetchone()
            if row is None:
                await self.save_vc_settings(guild_id)
                return defaults
            return {
                'enabled': bool(row[1]) if len(row) > 1 else True,
                'channel_id': row[2] if len(row) > 2 else None,
                'level_message': (row[3] if len(row) > 3 else None) or DEFAULT_VC_MESSAGE,
                'min_xp': row[4] if len(row) > 4 and row[4] is not None else 10,
                'max_xp': row[5] if len(row) > 5 and row[5] is not None else 20,
            }
        except Exception as e:
            logger.error(f"Error getting VC settings: {e}")
            return defaults

    async def save_vc_settings(self, guild_id, **fields):
        allowed = ('enabled', 'channel_id', 'level_message', 'min_xp', 'max_xp')
        updates = {key: value for key, value in fields.items() if key in allowed}
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO vc_settings (guild_id) VALUES (?)", (guild_id,)
                )
                if updates:
                    assignments = ", ".join(f"{name} = ?" for name in updates)
                    await db.execute(
                        f"UPDATE vc_settings SET {assignments} WHERE guild_id = ?",
                        (*updates.values(), guild_id),
                    )
                await db.commit()
        except Exception as e:
            logger.error(f"Error saving VC settings: {e}")

    async def _send_level_message(self, channel, guild, member, new_level, message, earned_roles=None):
        """Send a level-up message as plain text.

        The message is always the message content. ``{embed:name}`` attaches a
        saved embed and ``{cv2:name}`` turns the message into that Components V2
        layout with the text shown above the container. Mentions never ping.
        """
        prefix = None
        try:
            config = await getConfig(guild.id)
            prefix = config.get('prefix') if isinstance(config, dict) else None
        except Exception:
            prefix = None

        seen = set()
        mentions = []
        for role in earned_roles or []:
            if role is not None and role.id not in seen:
                seen.add(role.id)
                mentions.append(role.mention)

        extra = {
            'level': str(new_level),
            'username': member.display_name,
            'server': guild.name,
            'earned': ", ".join(mentions),
        }
        no_pings = discord.AllowedMentions.none()
        template = message or "Congratulations {user}! You have reached level {level}!"

        variables = build_variables(
            user=member, guild=guild, channel=channel, bot=self.bot, prefix=prefix, extra=extra
        )
        text, embed_name, cv2_name = find_template_tokens(template)
        content = render(text, variables, guild=guild)

        if cv2_name:
            row = await get_template(guild.id, cv2_name)
            if row is None:
                logger.error(f"Level-up layout `{cv2_name}` no longer exists")
            else:
                try:
                    view = build_view(
                        row['data'],
                        template_id=row['id'],
                        placeholders=variables,
                        prefix_text=content or None,
                    )
                    await channel.send(view=view, allowed_mentions=no_pings)
                    return
                except Exception as e:
                    logger.error(f"Level-up layout `{cv2_name}` failed: {e}")

        embeds = []
        if embed_name:
            saved = await get_embed(guild.id, embed_name)
            if saved is None:
                logger.error(f"Level-up embed `{embed_name}` no longer exists")
            else:
                try:
                    embeds.append(render_embed(saved['data'], variables))
                except Exception as e:
                    logger.error(f"Level-up embed `{embed_name}` failed: {e}")

        if not content and not embeds:
            return

        await channel.send(
            content=content or None,
            embeds=embeds or None,
            allowed_mentions=no_pings,
        )

    async def announce_vc_level_up(self, guild, member, new_level, settings, fallback_channel=None,
                                   *, destination=None, earned_roles=None):
        """Announce a voice level up using the voice settings, never the chat ones."""
        channel = destination
        if channel is None:
            channel_id = settings.get('channel_id')
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel and not channel.permissions_for(guild.me).send_messages:
                    logger.warning(f"No permission to send messages in the VC level channel {channel_id}")
                    channel = None
            if channel is None:
                channel = fallback_channel
        if channel is None:
            logger.error("No usable channel for the VC level-up message")
            return

        if earned_roles is None:
            earned_roles = await self.give_vc_rewards(guild, member, new_level)

        await self._send_level_message(
            channel, guild, member, new_level,
            settings.get('level_message'), earned_roles,
        )

    async def _vc_user_data(self, guild_id, user_id):
        """Return (xp, level, minutes) for a member's voice activity."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT xp, minutes FROM vc_xp WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id),
                ) as cursor:
                    row = await cursor.fetchone()
            if not row:
                return 0, 0, 0
            xp = row[0] or 0
            return xp, calculate_level_from_xp(xp), (row[1] or 0)
        except Exception as e:
            logger.error(f"Error getting VC data: {e}")
            return 0, 0, 0

    async def _vc_user_rank(self, guild_id, user_id):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT COUNT(*) + 1 FROM vc_xp WHERE guild_id = ? AND xp > "
                    "(SELECT COALESCE(xp, 0) FROM vc_xp WHERE guild_id = ? AND user_id = ?)",
                    (guild_id, guild_id, user_id),
                ) as cursor:
                    return (await cursor.fetchone())[0]
        except Exception as e:
            logger.error(f"Error getting VC rank: {e}")
            return 1

    async def get_vc_xp_multiplier(self, guild_id, user_id, channel_id):
        """Voice XP multiplier from the VC tables, independent of chat multipliers."""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return 1.0

            member = guild.get_member(user_id)
            if not member:
                return 1.0

            total_multiplier = 1.0
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT target_id, multiplier FROM vc_xp_multipliers WHERE guild_id = ? AND target_type = 'role'",
                    (guild_id,),
                ) as cursor:
                    role_multipliers = await cursor.fetchall()

                for role_id, multiplier in role_multipliers:
                    if any(role.id == role_id for role in member.roles):
                        total_multiplier *= multiplier

                if channel_id:
                    async with db.execute(
                        "SELECT multiplier FROM vc_xp_multipliers WHERE guild_id = ? AND target_id = ? AND target_type = 'channel'",
                        (guild_id, channel_id),
                    ) as cursor:
                        channel_mult = await cursor.fetchone()
                        if channel_mult:
                            total_multiplier *= channel_mult[0]

            return total_multiplier
        except Exception as e:
            logger.error(f"Error getting VC XP multiplier: {e}")
            return 1.0

    async def give_vc_rewards(self, guild, member, level):
        """Give the voice-level reward roles. Returns the roles added."""
        granted = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT role_id, remove_previous FROM vc_level_rewards WHERE guild_id = ? AND level <= ? ORDER BY level DESC",
                    (guild.id, level),
                ) as cursor:
                    rewards = await cursor.fetchall()

            for role_id, remove_previous in rewards:
                role = guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason=f"Voice level {level} reward")
                        granted.append(role)
                    except discord.Forbidden:
                        logger.warning(f"No permission to add VC reward role {role.name} to {member}")
                        continue
                    except discord.HTTPException as e:
                        logger.error(f"Failed to add VC reward role {role.name} to {member}: {e}")
                        continue

                    if remove_previous:
                        async with aiosqlite.connect(self.db_path) as db:
                            async with db.execute(
                                "SELECT role_id FROM vc_level_rewards WHERE guild_id = ? AND level < ?",
                                (guild.id, level),
                            ) as cursor:
                                prev_rewards = await cursor.fetchall()

                        for prev_role_id, in prev_rewards:
                            prev_role = guild.get_role(prev_role_id)
                            if prev_role and prev_role in member.roles:
                                try:
                                    await member.remove_roles(prev_role, reason=f"Upgraded to voice level {level}")
                                except discord.HTTPException as e:
                                    logger.error(f"Failed to remove previous VC reward role {prev_role.name}: {e}")

        except Exception as e:
            logger.error(f"Error giving VC level rewards: {e}")
        return granted

    async def _award_vc_minute(self, guild, member, settings, fallback_channel=None):
        """Give one minute of voice XP, announcing a level up when it happens."""
        xp_low = int(settings.get('min_xp', 10) or 10)
        xp_high = int(settings.get('max_xp', 20) or xp_low)
        if xp_low > xp_high:
            xp_low, xp_high = xp_high, xp_low
        xp_gain = random.randint(max(1, xp_low), max(1, xp_high))
        multiplier = await self.get_vc_xp_multiplier(
            guild.id, member.id, getattr(fallback_channel, 'id', None)
        )
        if multiplier and multiplier != 1.0:
            xp_gain = max(1, int(round(xp_gain * multiplier)))
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT xp, minutes FROM vc_xp WHERE guild_id = ? AND user_id = ?",
                (guild.id, member.id),
            ) as cursor:
                row = await cursor.fetchone()
            old_xp = (row[0] or 0) if row else 0
            minutes = (row[1] or 0) if row else 0
            old_level = calculate_level_from_xp(old_xp)
            new_xp = old_xp + xp_gain
            new_level = calculate_level_from_xp(new_xp)
            await db.execute(
                "INSERT OR REPLACE INTO vc_xp (guild_id, user_id, xp, minutes) VALUES (?, ?, ?, ?)",
                (guild.id, member.id, new_xp, minutes + 1),
            )
            await db.commit()

        if new_level > old_level:
            # Voice levels use their own message and grant only VC rewards.
            await self.announce_vc_level_up(
                guild, member, new_level, settings, fallback_channel
            )

    @tasks.loop(minutes=1)
    async def vc_loop(self):
        await self.bot.wait_until_ready()
        for guild in list(self.bot.guilds):
            try:
                settings = await self.get_vc_settings(guild.id)
                if not settings.get('enabled'):
                    continue
                afk_id = guild.afk_channel.id if guild.afk_channel else None
                for channel in guild.voice_channels:
                    if afk_id is not None and channel.id == afk_id:
                        continue
                    for member in list(channel.members):
                        if member.bot:
                            continue
                        state = member.voice
                        if state is None or state.self_deaf or state.deaf or state.afk:
                            continue
                        await self._award_vc_minute(guild, member, settings, channel)
            except Exception as e:
                logger.error(f"VC level loop error for guild {guild.id}: {e}")

    async def _send_rank(self, ctx, member, kind):
        guild_id = ctx.guild.id
        if kind == "vc":
            xp, level, minutes = await self._vc_user_data(guild_id, member.id)
            rank = await self._vc_user_rank(guild_id, member.id)
            title = "VC Rank"
            count_label = "Voice minutes"
            count_value = f"{minutes:,}"
        else:
            xp, level, messages = await self.get_user_data(guild_id, member.id)
            rank = await self.get_user_rank(guild_id, member.id)
            title = "Chat Rank"
            count_label = "Messages"
            count_value = f"{messages:,}"

        _, progress, needed = get_level_progress(xp)
        percentage = (progress / needed * 100) if needed > 0 else 100

        embed = discord.Embed(
            title=f"📊 {title} — {member.display_name}",
            color=0xFF0000,
            timestamp=datetime.now(IST),
        )
        embed.add_field(name="Level", value=f"{level:,}", inline=True)
        embed.add_field(name="XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="Rank", value=f"#{rank:,}", inline=True)
        embed.add_field(name=count_label, value=count_value, inline=True)
        embed.add_field(
            name=f"Progress to level {level + 1}",
            value=f"{get_progress_bar(progress, needed, 12)} {percentage:.1f}% ({progress:,}/{needed:,} XP)",
            inline=False,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="chatrank", aliases=["cl"], description="Show chat level and rank")
    async def chatlevel(self, ctx, member: Optional[discord.Member] = None):
        await self._send_rank(ctx, member or ctx.author, "chat")

    @commands.hybrid_command(name="rankchat", aliases=["rc"], description="Show a basic chat rank")
    async def rankchat(self, ctx, member: Optional[discord.Member] = None):
        await self._send_rank(ctx, member or ctx.author, "chat")

    @commands.hybrid_group(name="vclevel", aliases=["vl"], invoke_without_command=True,
                           description="Voice level, rank and setup")
    async def vclevel(self, ctx, member: Optional[discord.Member] = None):
        if ctx.invoked_subcommand is None:
            await self._send_rank(ctx, member or ctx.author, "vc")

    @vclevel.command(name="settings", description="Open the VC leveling setup popup")
    @commands.has_permissions(administrator=True)
    async def vc_settings(self, ctx):
        try:
            current = await self.get_vc_settings(ctx.guild.id)
            interaction = getattr(ctx, 'interaction', None)
            if interaction is not None:
                await interaction.response.send_modal(VCConfigModal(self, current))
                return
            embed = discord.Embed(
                title="⚙️ VC Leveling Settings",
                description="Press the button below to open the popup.\n"
                            "Voice XP, the VC level-up text and the channel are all edited there.",
                color=0xFF0000,
                timestamp=datetime.now(IST),
            )
            embed.add_field(name="Current Settings", value=_vc_summary(current), inline=False)
            await ctx.send(embed=embed, view=SettingsLauncherView(lambda: VCConfigModal(self, current)))
        except Exception as e:
            logger.error(f"Error in VC settings command: {e}")

    @vclevel.command(name="channel", description="Set the VC level-up channel")
    @commands.has_permissions(administrator=True)
    async def vc_channel(self, ctx, channel: discord.TextChannel):
        await self.save_vc_settings(ctx.guild.id, channel_id=channel.id)
        await ctx.send(f"✅ VC level-up messages will now be sent in {channel.mention}.")

    @vclevel.command(name="setxp", description="Set voice XP per minute (a number or a range like 10-20)")
    @commands.has_permissions(administrator=True)
    async def vc_setxp(self, ctx, amount: str):
        parsed = parse_xp_range(amount)
        if parsed is None:
            await ctx.send(f"{CROSS} Use a number like `15` or a range like `10-20` (each 1-999).")
            return
        low, high = parsed
        await self.save_vc_settings(ctx.guild.id, min_xp=low, max_xp=high)
        xp_text = str(low) if low == high else f"{low}-{high}"
        await ctx.send(f"✅ Voice XP per minute is now **{xp_text}**.")

    @vclevel.command(name="setmessage", description="Set the VC level-up text message")
    @commands.has_permissions(administrator=True)
    async def vc_setmessage(self, ctx, *, message: str):
        if len(message) > 2000:
            await ctx.send(f"{CROSS} The VC level-up message must be under 2000 characters.")
            return
        await self.save_vc_settings(ctx.guild.id, level_message=message)
        await ctx.send(f"✅ VC level-up message set to:\n```{message}```")

    @vclevel.command(name="enable", description="Enable voice leveling")
    @commands.has_permissions(administrator=True)
    async def vc_enable(self, ctx):
        await self.save_vc_settings(ctx.guild.id, enabled=1)
        await ctx.send("✅ Voice leveling is now **enabled**.")

    @vclevel.command(name="disable", description="Disable voice leveling")
    @commands.has_permissions(administrator=True)
    async def vc_disable(self, ctx):
        await self.save_vc_settings(ctx.guild.id, enabled=0)
        await ctx.send("🛑 Voice leveling is now **disabled**.")

    @vclevel.command(name="test", description="Preview the VC level-up message")
    @commands.has_permissions(manage_guild=True)
    async def vc_test(self, ctx):
        settings = await self.get_vc_settings(ctx.guild.id)
        _xp, level, _minutes = await self._vc_user_data(ctx.guild.id, ctx.author.id)
        preview_roles = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role_id FROM vc_level_rewards WHERE guild_id = ? AND level = ?",
                (ctx.guild.id, level + 1),
            ) as cursor:
                row = await cursor.fetchone()
        if row:
            role = ctx.guild.get_role(row[0])
            if role:
                preview_roles.append(role)

        await self.announce_vc_level_up(
            ctx.guild, ctx.author, level + 1, settings, ctx.channel,
            destination=ctx.channel, earned_roles=preview_roles,
        )
        await ctx.send("-# Preview only — no roles were granted and no XP changed.")

    @vclevel.command(name="overview", description="Show VC leveling settings, rewards and multipliers in one panel")
    @commands.has_permissions(manage_guild=True)
    async def vc_overview(self, ctx):
        await ctx.send(embed=await self.build_vc_overview(ctx.guild))

    @vclevel.command(name="leaderboard", aliases=["lb"], description="Show the voice leaderboard")
    async def vc_leaderboard(self, ctx):
        rows, label = await self._top_rows(ctx.guild.id, "vc")
        await ctx.send(view=self._leaderboard_view(ctx.guild, rows, "vc", label))

    @vclevel.group(name="rewards", invoke_without_command=True, description="Manage VC level rewards")
    async def vc_rewards(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @vc_rewards.command(name="add", description="Add a VC level reward")
    @commands.has_permissions(administrator=True)
    async def vc_rewards_add(self, ctx, level: int, role: discord.Role, remove_previous: bool = False):
        if level <= 0:
            await ctx.send("Level must be greater than 0.")
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO vc_level_rewards (guild_id, level, role_id, remove_previous) VALUES (?, ?, ?, ?)",
                (ctx.guild.id, level, role.id, int(remove_previous)),
            )
            await db.commit()
        await ctx.send(
            f"Added VC reward {role.mention} for voice level {level} (Remove Previous: {remove_previous})"
        )

    @vc_rewards.command(name="remove", description="Remove a VC level reward")
    @commands.has_permissions(administrator=True)
    async def vc_rewards_remove(self, ctx, level: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM vc_level_rewards WHERE guild_id = ? AND level = ?",
                (ctx.guild.id, level),
            )
            await db.commit()
        await ctx.send(f"Removed the VC reward for voice level {level}.")

    @vc_rewards.command(name="list", description="List all VC level rewards")
    @commands.has_permissions(administrator=True)
    async def vc_rewards_list(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT level, role_id, remove_previous FROM vc_level_rewards WHERE guild_id = ? ORDER BY level",
                (ctx.guild.id,),
            ) as cursor:
                rewards = await cursor.fetchall()

        if not rewards:
            await ctx.send("No VC level rewards configured.")
            return

        embed = discord.Embed(title="VC Level Rewards", color=0xFF0000, timestamp=datetime.now(IST))
        for level, role_id, remove_previous in rewards:
            role = ctx.guild.get_role(role_id)
            role_name = role.mention if role else "Role not found"
            embed.add_field(
                name=f"Voice Level {level}",
                value=f"Role: {role_name} (Remove Previous: {remove_previous})",
                inline=False,
            )
        await ctx.send(embed=embed)

    @vclevel.group(name="multiplier", invoke_without_command=True, description="Manage VC XP multipliers")
    async def vc_multiplier(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    def _resolve_vc_multiplier_target(self, guild, target_type, raw):
        digits = re.sub(r"\D", "", raw or "")
        if target_type == "role":
            role = guild.get_role(int(digits)) if digits else None
            if role is None and raw:
                role = discord.utils.find(
                    lambda r: r.name.lower() == raw.lstrip("@").lower(), guild.roles
                )
            return role
        channel = guild.get_channel(int(digits)) if digits else None
        if channel is None and raw:
            channel = discord.utils.get(guild.voice_channels, name=raw.lstrip("#").lower())
        return channel

    @vc_multiplier.command(name="add", description="Add a VC XP multiplier (role or channel)")
    @commands.has_permissions(administrator=True)
    async def vc_multiplier_add(self, ctx, target_type: str, target: str, multiplier: float):
        target_type = target_type.lower()
        if target_type not in ("role", "channel"):
            await ctx.send("Invalid target type. Must be 'role' or 'channel'.")
            return
        if multiplier <= 0:
            await ctx.send("Multiplier must be greater than 0.")
            return

        resolved = self._resolve_vc_multiplier_target(ctx.guild, target_type, target)
        if resolved is None:
            await ctx.send(f"I couldn't find that {target_type}.")
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO vc_xp_multipliers (guild_id, target_id, target_type, multiplier) VALUES (?, ?, ?, ?)",
                (ctx.guild.id, resolved.id, target_type, multiplier),
            )
            await db.commit()

        await ctx.send(f"Added a **{multiplier}x** voice XP multiplier for {target_type} {resolved.mention}.")

    @vc_multiplier.command(name="remove", description="Remove a VC XP multiplier")
    @commands.has_permissions(administrator=True)
    async def vc_multiplier_remove(self, ctx, target_type: str, target: str):
        target_type = target_type.lower()
        if target_type not in ("role", "channel"):
            await ctx.send("Invalid target type. Must be 'role' or 'channel'.")
            return

        resolved = self._resolve_vc_multiplier_target(ctx.guild, target_type, target)
        if resolved is None:
            await ctx.send(f"I couldn't find that {target_type}.")
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM vc_xp_multipliers WHERE guild_id = ? AND target_id = ? AND target_type = ?",
                (ctx.guild.id, resolved.id, target_type),
            )
            await db.commit()
        await ctx.send(f"Removed the voice XP multiplier for {target_type} {resolved.mention}.")

    @vc_multiplier.command(name="list", description="List all VC XP multipliers")
    @commands.has_permissions(administrator=True)
    async def vc_multiplier_list(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT target_id, target_type, multiplier FROM vc_xp_multipliers WHERE guild_id = ?",
                (ctx.guild.id,),
            ) as cursor:
                multipliers = await cursor.fetchall()

        if not multipliers:
            await ctx.send("No VC XP multipliers configured.")
            return

        embed = discord.Embed(title="VC XP Multipliers", color=0xFF0000, timestamp=datetime.now(IST))
        for target_id, target_type, multiplier in multipliers:
            if target_type == "role":
                target_obj = ctx.guild.get_role(target_id)
            else:
                target_obj = ctx.guild.get_channel(target_id)
            target_name = target_obj.mention if target_obj else "Not found"
            embed.add_field(
                name=f"{target_type.capitalize()}: {target_name}",
                value=f"Multiplier: {multiplier}x",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="vcleaderboard", aliases=["vclb"], description="Show the voice leaderboard")
    async def vcleaderboard_cmd(self, ctx):
        rows, label = await self._top_rows(ctx.guild.id, "vc")
        await ctx.send(view=self._leaderboard_view(ctx.guild, rows, "vc", label))

    @commands.hybrid_command(name="rankvc", aliases=["rv"], description="Show a basic voice rank")
    async def rankvc(self, ctx, member: Optional[discord.Member] = None):
        await self._send_rank(ctx, member or ctx.author, "vc")

    # ── Leaderboards ──────────────────────────────────────────────────────

    async def _top_rows(self, guild_id, kind, limit=10):
        if kind == "vc":
            table, count_column, label = "vc_xp", "minutes", "voice minutes"
        else:
            table, count_column, label = "user_xp", "messages", "messages"
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f"SELECT user_id, xp, COALESCE({count_column}, 0) FROM {table} "
                "WHERE guild_id = ? AND xp > 0 ORDER BY xp DESC LIMIT ?",
                (guild_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return rows, label

    def _leaderboard_container(self, guild, rows, kind, label, limit=10):
        """One CV2 container: server icon + name, a divider, then the top entries."""
        title = "VC Leaderboard" if kind == "vc" else "Chat Leaderboard"
        lines = []
        for position, (user_id, xp, count) in enumerate(rows, start=1):
            member = guild.get_member(user_id)
            name = member.display_name if member else f"user {user_id}"
            lines.append(
                f"`{position:02d}` **{name}** — Level {calculate_level_from_xp(xp)} · "
                f"{xp:,} XP · {count:,} {label}"
            )

        body = "\n".join(lines) if lines else "No data yet — start chatting or join a voice channel!"
        note = f"Top {limit} • {datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')}"

        container = discord.ui.Container(accent_color=0xFF0000)
        header = discord.ui.TextDisplay(f"**{guild.name}**\n🏆 {title}")
        icon = guild.icon.url if guild.icon else None
        if icon:
            container.add_item(discord.ui.Section(header, accessory=discord.ui.Thumbnail(icon)))
        else:
            container.add_item(header)
        container.add_item(discord.ui.Separator(visible=True))
        container.add_item(discord.ui.TextDisplay(body))
        container.add_item(discord.ui.Separator(visible=True))
        container.add_item(discord.ui.TextDisplay(f"*{note}*"))
        return container

    def _leaderboard_view(self, guild, rows, kind, label, limit=10):
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(self._leaderboard_container(guild, rows, kind, label, limit))
        return view

    async def _both_leaderboard_view(self, guild, limit=10):
        chat_rows, chat_label = await self._top_rows(guild.id, "chat", limit)
        vc_rows, vc_label = await self._top_rows(guild.id, "vc", limit)
        view = discord.ui.LayoutView(timeout=None)
        view.add_item(self._leaderboard_container(guild, chat_rows, "chat", chat_label, limit))
        view.add_item(self._leaderboard_container(guild, vc_rows, "vc", vc_label, limit))
        return view

    @commands.hybrid_group(name="leaderboard", aliases=["lb"], invoke_without_command=True, description="Chat and voice leaderboards")
    async def leaderboard(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @leaderboard.command(name="chat", description="Show the chat leaderboard")
    async def leaderboard_chat(self, ctx):
        rows, label = await self._top_rows(ctx.guild.id, "chat")
        await ctx.send(view=self._leaderboard_view(ctx.guild, rows, "chat", label))

    @leaderboard.command(name="vc", description="Show the voice leaderboard")
    async def leaderboard_vc(self, ctx):
        rows, label = await self._top_rows(ctx.guild.id, "vc")
        await ctx.send(view=self._leaderboard_view(ctx.guild, rows, "vc", label))

    @staticmethod
    def _parse_hhmm(raw):
        match = re.match(r"^(\d{1,2})[:.](\d{2})$", (raw or "").strip())
        if not match:
            return None
        hour, minute = int(match.group(1)), int(match.group(2))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            return None
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _parse_weekday(raw):
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        raw = (raw or "").strip().lower()
        if raw.isdigit() and 0 <= int(raw) <= 6:
            return int(raw)
        return days.index(raw) if raw in days else None

    @staticmethod
    def _find_text_channel(guild, raw):
        if guild is None or not raw:
            return None
        match = re.search(r"<#(\d+)>", raw)
        if match:
            return guild.get_channel(int(match.group(1)))
        match = re.search(r"\d{15,25}", raw)
        if match:
            return guild.get_channel(int(match.group(0)))
        return discord.utils.get(guild.text_channels, name=raw.strip().lstrip("#"))

    async def save_leaderboard_schedule(self, guild_id, channel_id, period, weekday, time_ist):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO leaderboard_settings (guild_id) VALUES (?)", (guild_id,))
            await db.execute(
                "UPDATE leaderboard_settings SET channel_id = ?, period = ?, weekday = ?, time_ist = ?, last_posted = NULL WHERE guild_id = ?",
                (channel_id, period, weekday, time_ist, guild_id),
            )
            await db.commit()

    @staticmethod
    def _schedule_confirmation(channel, period, weekday, time_ist):
        if period == "weekly" and weekday is not None:
            when = f"every {DAY_NAMES[weekday]}"
        else:
            when = "every day"
        return f"Posts {when} at **{time_ist} IST** in {channel.mention} — chat and VC leaderboards together."

    async def _schedule_summary(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT channel_id, period, weekday, time_ist FROM leaderboard_settings WHERE guild_id = ?",
                (guild_id,),
            ) as cursor:
                row = await cursor.fetchone()
        if not row or not row[0] or not row[1] or not row[3]:
            return "No schedule set."
        channel_id, period, weekday, time_ist = row
        if period == "weekly" and weekday is not None and 0 <= weekday < len(DAY_NAMES):
            when = f"every {DAY_NAMES[weekday]}"
        else:
            when = "every day"
        return f"<#{channel_id}> — {when} at **{time_ist} IST**."

    @staticmethod
    def _clamp_interval(minutes):
        try:
            value = int(minutes)
        except (TypeError, ValueError):
            return 30
        return max(1, min(value, 1440))

    async def get_live_interval(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT live_interval FROM leaderboard_settings WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
        return self._clamp_interval(row[0] if row and row[0] is not None else 30)

    async def start_live_leaderboard(self, guild, channel, interval=None):
        view = await self._both_leaderboard_view(guild)
        message = await channel.send(view=view)
        stamp = datetime.now(IST).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO leaderboard_settings (guild_id) VALUES (?)", (guild.id,))
            if interval is None:
                await db.execute(
                    "UPDATE leaderboard_settings SET live_channel_id = ?, live_message_id = ?, live_last_posted = ? WHERE guild_id = ?",
                    (channel.id, message.id, stamp, guild.id),
                )
            else:
                await db.execute(
                    "UPDATE leaderboard_settings SET live_channel_id = ?, live_message_id = ?, live_interval = ?, live_last_posted = ? WHERE guild_id = ?",
                    (channel.id, message.id, self._clamp_interval(interval), stamp, guild.id),
                )
            await db.commit()
        return message

    async def _live_summary(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT live_channel_id, live_interval FROM leaderboard_settings WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row or not row[0]:
            return "Not running."
        interval = self._clamp_interval(row[1] if len(row) > 1 else 30)
        plural = "" if interval == 1 else "s"
        return f"Updating every {interval} minute{plural} in <#{row[0]}>."

    @leaderboard.command(name="schedule", description="Schedule daily or weekly leaderboard posts (IST)")
    @commands.has_permissions(manage_guild=True)
    async def leaderboard_schedule(self, ctx, channel: Optional[discord.TextChannel] = None,
                                   period: Optional[str] = None, day: Optional[str] = None,
                                   time: Optional[str] = None):
        if period and period.lower() in ("off", "disable", "stop", "none"):
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE leaderboard_settings SET channel_id = NULL, period = NULL, weekday = NULL, time_ist = NULL, last_posted = NULL WHERE guild_id = ?",
                    (ctx.guild.id,),
                )
                await db.commit()
            await ctx.send("🛑 Scheduled leaderboard posts are now off.")
            return

        # Fully specified on the command line: save it without asking anything.
        if channel is not None and period is not None and time is not None:
            period = period.lower().strip()
            if period not in ("daily", "weekly"):
                await ctx.send("Period must be `daily` or `weekly`.")
                return
            weekday = None
            if period == "weekly":
                weekday = self._parse_weekday(day) if day else None
                if weekday is None:
                    await ctx.send("That day isn't valid — use monday to sunday.")
                    return
            time_ist = self._parse_hhmm(time)
            if time_ist is None:
                await ctx.send("That time isn't valid — use 24-hour `HH:MM`, e.g. `20:30`.")
                return
            await self.save_leaderboard_schedule(ctx.guild.id, channel.id, period, weekday, time_ist)
            await ctx.send(f"✅ {self._schedule_confirmation(channel, period, weekday, time_ist)}")
            return

        # Anything missing is collected in a popup instead of chat questions.
        build_modal = lambda: LeaderboardScheduleModal(
            self, ctx.guild,
            channel.mention if channel else None,
            period, day, time,
        )

        interaction = getattr(ctx, 'interaction', None)
        if interaction is not None:
            await interaction.response.send_modal(build_modal())
            return

        embed = discord.Embed(
            title="🗓️ Leaderboard Schedule",
            description="Press the button below to open the schedule popup.\n"
                        "Times are IST, and each post includes both the chat and VC leaderboards.",
            color=0xFF0000,
            timestamp=datetime.now(IST),
        )
        embed.add_field(name="Current", value=await self._schedule_summary(ctx.guild.id), inline=False)
        await ctx.send(embed=embed, view=SettingsLauncherView(build_modal, label="Set Schedule", emoji="🗓️"))

    @leaderboard.command(name="live", description="Post a leaderboard that refreshes on a configurable interval")
    @commands.has_permissions(manage_guild=True)
    async def leaderboard_live(self, ctx, channel: Optional[discord.TextChannel] = None,
                               action: Optional[str] = None, interval: Optional[int] = None):
        if action and action.lower() in ("off", "disable", "stop"):
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE leaderboard_settings SET live_channel_id = NULL, live_message_id = NULL, live_last_posted = NULL WHERE guild_id = ?",
                    (ctx.guild.id,),
                )
                await db.commit()
            await ctx.send("🛑 Live leaderboard updates are now off.")
            return

        # `leaderboard live #chan 15` passes the interval through the action slot.
        if interval is None and action and action.strip().isdigit():
            interval = int(action)

        if channel is not None:
            minutes = await self.get_live_interval(ctx.guild.id) if interval is None else self._clamp_interval(interval)
            await self.start_live_leaderboard(ctx.guild, channel, interval)
            plural = "" if minutes == 1 else "s"
            await ctx.send(f"✅ Live leaderboard started in {channel.mention} — it refreshes every {minutes} minute{plural} (chat + VC).")
            return

        current_interval = await self.get_live_interval(ctx.guild.id)
        build_modal = lambda: LeaderboardLiveModal(self, ctx.guild, ctx.channel, current_interval)

        interaction = getattr(ctx, 'interaction', None)
        if interaction is not None:
            await interaction.response.send_modal(build_modal())
            return

        embed = discord.Embed(
            title="📡 Live Leaderboard",
            description="Press the button below to pick the channel and refresh interval in a popup.\n"
                        "The panel shows the chat and VC leaderboards.",
            color=0xFF0000,
            timestamp=datetime.now(IST),
        )
        embed.add_field(name="Current", value=await self._live_summary(ctx.guild.id), inline=False)
        await ctx.send(embed=embed, view=SettingsLauncherView(build_modal, label="Start Live Panel", emoji="📡"))

    @leaderboard.command(name="liveinterval", aliases=["liveint"], description="Change how often the live leaderboard refreshes")
    @commands.has_permissions(manage_guild=True)
    async def leaderboard_live_interval(self, ctx, minutes: int):
        if minutes < 1 or minutes > 1440:
            await ctx.send(f"{CROSS} The interval must be between 1 and 1440 minutes.")
            return

        value = self._clamp_interval(minutes)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT live_channel_id FROM leaderboard_settings WHERE guild_id = ?", (ctx.guild.id,)
            ) as cursor:
                row = await cursor.fetchone()
            if not row or not row[0]:
                await ctx.send("No live leaderboard is running — start one with `leaderboard live`.")
                return
            await db.execute(
                "UPDATE leaderboard_settings SET live_interval = ?, live_last_posted = ? WHERE guild_id = ?",
                (value, datetime.now(IST).isoformat(), ctx.guild.id),
            )
            await db.commit()

        plural = "" if value == 1 else "s"
        await ctx.send(f"✅ Live leaderboard now refreshes every {value} minute{plural}.")

    @tasks.loop(minutes=1)
    async def schedule_loop(self):
        await self.bot.wait_until_ready()
        now = datetime.now(IST)
        stamp = now.strftime("%Y-%m-%d")
        for guild in list(self.bot.guilds):
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute(
                        "SELECT channel_id, period, weekday, time_ist, last_posted FROM leaderboard_settings WHERE guild_id = ?",
                        (guild.id,),
                    ) as cursor:
                        row = await cursor.fetchone()
                if not row:
                    continue
                channel_id, period, weekday, time_ist, last_posted = row
                if not channel_id or not period or not time_ist or last_posted == stamp:
                    continue
                try:
                    hour, minute = (int(part) for part in time_ist.split(":"))
                except (ValueError, AttributeError):
                    continue
                now_minutes = now.hour * 60 + now.minute
                if not 0 <= now_minutes - (hour * 60 + minute) < 10:
                    continue
                if period == "weekly" and weekday is not None and now.weekday() != weekday:
                    continue
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    continue
                await channel.send(view=await self._both_leaderboard_view(guild))
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "UPDATE leaderboard_settings SET last_posted = ? WHERE guild_id = ?",
                        (stamp, guild.id),
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Scheduled leaderboard error for guild {guild.id}: {e}")

    @tasks.loop(minutes=1)
    async def live_loop(self):
        await self.bot.wait_until_ready()
        now = datetime.now(IST)
        for guild in list(self.bot.guilds):
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute(
                        "SELECT live_channel_id, live_message_id, live_interval, live_last_posted FROM leaderboard_settings WHERE guild_id = ?",
                        (guild.id,),
                    ) as cursor:
                        row = await cursor.fetchone()
                if not row or not row[0]:
                    continue

                channel_id = row[0]
                message_id = row[1]
                interval = self._clamp_interval(row[2] if len(row) > 2 else 30)
                last_posted = row[3] if len(row) > 3 else None

                if last_posted:
                    try:
                        last = datetime.fromisoformat(last_posted)
                    except ValueError:
                        last = None
                    if last is not None:
                        if last.tzinfo is None:
                            last = last.replace(tzinfo=IST)
                        if (now - last).total_seconds() < interval * 60:
                            continue

                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    continue

                view = await self._both_leaderboard_view(guild)
                message = None
                if message_id:
                    try:
                        message = await channel.fetch_message(message_id)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        message = None
                if message is None:
                    message = await channel.send(view=view)
                else:
                    await message.edit(view=view)

                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "UPDATE leaderboard_settings SET live_message_id = ?, live_last_posted = ? WHERE guild_id = ?",
                        (message.id, now.isoformat(), guild.id),
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Live leaderboard error for guild {guild.id}: {e}")

    @level.command(name="test", description="Preview the level-up message without granting anything")
    @commands.has_permissions(manage_guild=True)
    async def level_test(self, ctx):
        """Preview the configured level-up message, embed/CV2 tokens included."""
        settings = await self.get_guild_settings(ctx.guild.id)
        _xp, level, _messages = await self.get_user_data(ctx.guild.id, ctx.author.id)
        test_level = level + 1

        earned = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role_id FROM level_rewards WHERE guild_id = ? AND level = ?",
                (ctx.guild.id, test_level),
            ) as cursor:
                row = await cursor.fetchone()
        if row:
            role = ctx.guild.get_role(row[0])
            if role:
                earned.append(role)

        await self.announce_level_up(
            ctx.guild, ctx.author, test_level, settings, ctx.channel,
            destination=ctx.channel, earned_roles=earned,
        )
        await ctx.send("-# Preview only — no roles were granted and no XP changed.")

