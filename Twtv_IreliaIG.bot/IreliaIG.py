# ================== IMPORTS ================== #
from twitchio.ext import commands
import requests
import asyncio
from datetime import datetime, timedelta
import pytz
import json
import time
import os

# ================== CONFIG ================== #
import logging
import configparser
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load configuration
config = configparser.ConfigParser()
config_file = 'bot_config.ini'

def load_config():
    """Load configuration from file or create default"""
    if os.path.exists(config_file):
        config.read(config_file)
        logger.info("Configuration loaded from file")
    else:
        # Create default config
        config.add_section('RIOT')
        config.set('RIOT', 'api_key', 'RGAPI-4b2d6c1f-584d-458a-8a55-177b8cf985c9')
        config.set('RIOT', 'game_name', 'estufa70')
        config.set('RIOT', 'tag_line', 'RPG')
        config.set('RIOT', 'region', 'europe')

        config.add_section('TWITCH')
        config.set('TWITCH', 'token', 'oauth:2f9fadpaonaizfwsbo2vg5eoqw25gc')
        config.set('TWITCH', 'channel', 'ruben_irpg')

        config.add_section('BOT')
        config.set('BOT', 'sleep_in_game', '25')
        config.set('BOT', 'sleep_out_game', '120')

        with open(config_file, 'w') as f:
            config.write(f)
        logger.info("Default configuration created")

load_config()

# Load from config
RIOT_API_KEY = config.get('RIOT', 'api_key')
GAME_NAME = config.get('RIOT', 'game_name')
TAG_LINE = config.get('RIOT', 'tag_line')
REGION = config.get('RIOT', 'region')

TWITCH_TOKEN = config.get('TWITCH', 'token')
CHANNEL = config.get('TWITCH', 'channel')

SLEEP_IN_GAME = config.getint('BOT', 'sleep_in_game')
SLEEP_OUT_GAME = config.getint('BOT', 'sleep_out_game')

# ================== CHAMPIONS ================== #
def cargar_campeones():
    url = "https://ddragon.leagueoflegends.com/cdn/13.24.1/data/en_US/champion.json"
    data = requests.get(url).json()["data"]

    champ_dict = {}
    for champ in data.values():
        champ_dict[int(champ["key"])] = champ["id"]

    return champ_dict

champions = cargar_campeones()

# ================== ANTI SPAM ================== #
cooldowns = {}

def can_use(user, command, seconds=3):
    key = f"{user}_{command}"
    now = time.time()

    if key in cooldowns and now - cooldowns[key] < seconds:
        return False

    cooldowns[key] = now
    return True

def has_permission(ctx, owner_only=False):
    """Check if user has permission: owner_only=True for owner only, False for owner and mods"""
    is_owner = ctx.author.name.lower() in ["ruben_irpg", "your_twitch_username"]
    if owner_only:
        return is_owner
    else:
        return is_owner or ctx.author.is_mod

def roman_to_int(roman):
    roman_map = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = 0
    prev_value = 0
    for char in reversed(roman.upper()):
        value = roman_map.get(char, 0)
        if value < prev_value:
            total -= value
        else:
            total += value
        prev_value = value
    return total

def format_rank(ranked_data):
    """Format rank data with better error handling"""
    if not ranked_data:
        return "Unranked"

    # Try solo queue first
    solo_queue = next((q for q in ranked_data if q.get("queueType") == "RANKED_SOLO_5x5"), None)
    if solo_queue:
        tier = solo_queue.get('tier', 'UNKNOWN').lower()
        rank_roman = solo_queue.get('rank', 'I')
        rank_num = roman_to_int(rank_roman)
        lp = solo_queue.get('leaguePoints', 0)
        wins = solo_queue.get('wins', 0)

        # Handle special cases
        if tier == 'master' or tier == 'grandmaster' or tier == 'challenger':
            return f"{tier} {lp}PL {wins} Wins"
        else:
            return f"{tier} {rank_num} {lp}PL {wins} Wins"

    # If no solo queue, try flex queue
    flex_queue = next((q for q in ranked_data if q.get("queueType") == "RANKED_FLEX_SR"), None)
    if flex_queue:
        tier = flex_queue.get('tier', 'UNKNOWN').lower()
        rank_roman = flex_queue.get('rank', 'I')
        rank_num = roman_to_int(rank_roman)
        lp = flex_queue.get('leaguePoints', 0)
        wins = flex_queue.get('wins', 0)
        return f"{tier} {rank_num} {lp}PL {wins} Wins (Flex)"

    return "Unranked"

def format_detailed_game_stats(player_data, match_data, game_type):
    """Format detailed game statistics like LouisGameDev's bot"""
    try:
        # Basic info
        champ = player_data["championName"]
        k = player_data["kills"]
        d = player_data["deaths"] 
        a = player_data["assists"]
        win = player_data["win"]
        
        # Position
        position = player_data.get("individualPosition", player_data.get("teamPosition", "UNKNOWN"))
        if position == "TOP":
            position = "Top"
        elif position == "JUNGLE":
            position = "Jungle"
        elif position == "MIDDLE":
            position = "Mid"
        elif position == "BOTTOM":
            position = "Bot"
        elif position == "UTILITY":
            position = "Support"
        
        # Result emoji
        result_emoji = "🏆Win" if win else "💀Lose"
        
        # Kill Participation
        team_id = player_data["teamId"]
        team_players = [p for p in match_data["info"]["participants"] if p["teamId"] == team_id]
        team_kills = sum(p["kills"] for p in team_players)
        kp = int((k + a) / team_kills * 100) if team_kills > 0 else 0
        
        # Total damage (format with k)
        total_dmg = player_data["totalDamageDealtToChampions"]
        dmg_str = f"{total_dmg/1000:.1f}k dmg" if total_dmg >= 1000 else f"{total_dmg} dmg"
        
        # Game duration (MM:SS)
        duration_sec = match_data["info"]["gameDuration"]
        minutes = duration_sec // 60
        seconds = duration_sec % 60
        duration_str = f"{minutes:02d}:{seconds:02d}"
        
        # CS per minute
        cs = player_data["totalMinionsKilled"] + player_data.get("totalAllyJungleMinionsKilled", 0) + player_data.get("totalEnemyJungleMinionsKilled", 0)
        cs_per_min = cs / (duration_sec / 60) if duration_sec > 0 else 0
        
        # Gold per minute
        gold = player_data["goldEarned"]
        gold_per_min = gold / (duration_sec / 60) if duration_sec > 0 else 0
        
        # Damage per minute
        dmg_per_min = total_dmg / (duration_sec / 60) if duration_sec > 0 else 0
        
        # Self-mitigated damage per minute
        self_mitigated = player_data.get("damageSelfMitigated", 0)
        self_mitigated_per_min = self_mitigated / (duration_sec / 60) if duration_sec > 0 else 0
        
        # CC time per minute
        cc_time = player_data.get("timeCCingOthers", 0)
        cc_per_min = cc_time / (duration_sec / 60) if duration_sec > 0 else 0
        
        # Vision score per minute
        vision_score = player_data.get("visionScore", 0)
        vision_per_min = vision_score / (duration_sec / 60) if duration_sec > 0 else 0
        
        # Format the message
        nickname = f"{GAME_NAME}#{TAG_LINE}"
        msg = f"{nickname} game results: {result_emoji} | {champ} | {position} | {k}/{d}/{a} | {kp}% KP | {dmg_str} | {duration_str} | {cs_per_min:.1f} cs/min | {gold_per_min:.0f} gold/min | {dmg_per_min/1000:.1f}k dmg/min | {self_mitigated_per_min/1000:.1f}k self-mitigated/min | {cc_per_min:.1f}s CC/min | {vision_per_min:.1f} vision/min"
        
        return msg
        
    except Exception as e:
        print(f"❌ Error formatting detailed stats: {e}")
        # Fallback to simple message
        champ = player_data.get("championName", "Unknown")
        k = player_data.get("kills", 0)
        d = player_data.get("deaths", 0)
        a = player_data.get("assists", 0)
        result = "🏆Win" if player_data.get("win", False) else "💀Lose"
        return f"{GAME_NAME}#{TAG_LINE} game results: {result} | {champ} | {k}/{d}/{a}"

def calculate_recent_ranked_stats(puuid, num_games=15):
    """Calculate KDA and winrate from last N ranked Solo Queue games"""
    try:
        matches = get_matches(puuid, count=num_games * 2)  # Get more to account for non-ranked games
        if not matches:
            return {"kda": 0, "winrate": 0, "games_analyzed": 0}
        
        # Load excluded matches
        cache_data = load_match_cache(puuid)
        excluded_matches = set(cache_data.get("excluded_matches", []))
        
        total_kills = 0
        total_deaths = 0
        total_assists = 0
        wins = 0
        games_analyzed = 0
        
        for match_id in matches:
            if games_analyzed >= num_games:
                break
                
            # Skip excluded matches
            if match_id in excluded_matches:
                continue
                
            match_data = get_match_data(match_id)
            if not match_data or "info" not in match_data:
                continue
            
            # Only ranked Solo Queue games
            if match_data["info"].get("queueId") != 420:
                continue
            
            # Skip remakes
            if match_data["info"]["gameDuration"] < 300:
                continue
            
            # Find player
            player = next((p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None)
            if not player:
                continue
            
            # Add to totals
            total_kills += player["kills"]
            total_deaths += player["deaths"]
            total_assists += player["assists"]
            
            if player["win"]:
                wins += 1
            
            games_analyzed += 1
        
        if games_analyzed == 0:
            return {"kda": 0, "winrate": 0, "games_analyzed": 0}
        
        # Calculate averages
        avg_kda = round((total_kills + total_assists) / total_deaths, 2) if total_deaths > 0 else total_kills + total_assists
        winrate = int((wins / games_analyzed) * 100)
        
        return {
            "kda": avg_kda,
            "winrate": winrate,
            "games_analyzed": games_analyzed
        }
        
    except Exception as e:
        print(f"❌ Error calculating recent ranked stats: {e}")
        return {"kda": 0, "winrate": 0, "games_analyzed": 0}

# ================== IRELIA DATA ================== #

def cargar_datos():
    try:
        with open("irelia_data.json", "r") as f:
            return json.load(f)
    except:
        return {"games": 288, "wins": 0, "last_match_id": ""}

def guardar_datos(data):
    with open("irelia_data.json", "w") as f:
        json.dump(data, f)

# ================== PERSISTENT STATS ================== #

PERSISTENT_FILE = "bot_persistent_stats.json"

def load_persistent_stats():
    """Load persistent stats from file"""
    if os.path.exists(PERSISTENT_FILE):
        try:
            with open(PERSISTENT_FILE, 'r') as f:
                data = json.load(f)
                # Convert session_start back to timestamp if it's a string
                if isinstance(data.get("session_start"), str):
                    data["session_start"] = datetime.fromisoformat(data["session_start"]).timestamp()
                return data
        except Exception as e:
            print(f"⚠️ Error loading persistent stats: {e}")
    return {}

def save_persistent_stats():
    """Save current stats to file"""
    data = {
        "win_streak": cache["win_streak"],
        "lose_streak": cache["lose_streak"],
        "max_win_streak": cache["max_win_streak"],
        "max_lose_streak": cache["max_lose_streak"],
        "last_game_id": cache["last_game_id"],
        "games": cache["games"]
    }
    try:
        with open(PERSISTENT_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print("💾 Streaks saved to disk")
    except Exception as e:
        print(f"⚠️ Error saving persistent stats: {e}")

def calculate_stats_from_api(puuid, hours=24):
    """Calculate wins/losses from API match history for last N hours"""
    try:
        # For all-time stats, get all matches; for recent, fewer
        count = None if hours == float('inf') else 100
        matches = get_matches(puuid, count=count)
        if not matches:
            return {"wins": 0, "losses": 0, "games": []}
        
        # Load excluded matches
        cache_data = load_match_cache(puuid)
        excluded_matches = set(cache_data.get("excluded_matches", []))
        
        wins = 0
        losses = 0
        games = []
        cutoff_time = datetime.now(pytz.timezone("UTC")) - timedelta(hours=hours)
        
        for i, match_id in enumerate(matches):
            if i % 100 == 0:
                print(f"DEBUG: Processing match {i+1}/{len(matches)}")
            match_data = get_match_data(match_id)
            if not match_data or "info" not in match_data:
                continue
            
            # Skip excluded matches
            if match_id in excluded_matches:
                print(f"DEBUG: Skipping excluded match {match_id}")
                continue
            
            # Only ranked games (queue_id 420 = RANKED_SOLO_5x5)
            if match_data["info"].get("queueId") != 420:
                continue
            
            # Check if match is within time window
            match_time = datetime.fromtimestamp(match_data["info"]["gameCreation"] / 1000, tz=pytz.timezone("UTC"))
            if match_time < cutoff_time and hours != float('inf'):
                break  # Stop checking older matches
            
            # Find player in match
            player = next((p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None)
            if not player:
                continue
            
            # Skip very short games (remakes)
            if match_data["info"]["gameDuration"] < 300:
                continue
            
            if player["win"]:
                wins += 1
                games.append("W")
            else:
                losses += 1
                games.append("L")
        
        print(f"DEBUG: Final stats: wins={wins}, losses={losses}")
        return {"wins": wins, "losses": losses, "games": games[:5]}
    except Exception as e:
        print(f"❌ Error calculating stats from API: {e}")
        return {"wins": 0, "losses": 0, "games": []}

def calculate_streak_from_api(puuid):
    """Calculate current win/lose streak from API match history"""
    try:
        matches = get_matches(puuid, count=100)  # Get last 100 matches for streak calculation
        if not matches:
            return {"win_streak": 0, "lose_streak": 0}
        
        # Load excluded matches
        cache_data = load_match_cache(puuid)
        excluded_matches = set(cache_data.get("excluded_matches", []))
        
        win_streak = 0
        lose_streak = 0
        
        for match_id in matches:
            # Skip excluded matches
            if match_id in excluded_matches:
                continue
                
            match_data = get_match_data(match_id)
            if not match_data or "info" not in match_data:
                continue
            
            # Only ranked games
            if match_data["info"].get("queueId") != 420:
                continue
            
            # Skip very short games
            if match_data["info"]["gameDuration"] < 300:
                continue
            
            # Find player in match
            player = next((p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None)
            if not player:
                continue
            
            if player["win"]:
                if lose_streak > 0:
                    break  # Streak was broken
                win_streak += 1
            else:
                if win_streak > 0:
                    break  # Streak was broken
                lose_streak += 1
        
        return {"win_streak": win_streak, "lose_streak": lose_streak}
    except Exception as e:
        print(f"❌ Error calculating streak from API: {e}")
        return {"win_streak": 0, "lose_streak": 0}

def initialize_ranked_stats(puuid):
    """Initialize ranked wins/losses from API on startup if cache is empty"""
    try:
        cache_data = load_match_cache(puuid)
        
        # If cache is empty or old (older than 1 hour), update it
        if not cache_data["matches"] or time.time() - cache_data["last_updated"] > 3600:
            print("🔄 Updating match cache on startup...")
            update_match_cache(puuid)
            cache_data = load_match_cache(puuid)
        
        # Update global cache
        cache["ranked_wins"] = cache_data["ranked_stats"]["wins"]
        cache["ranked_losses"] = cache_data["ranked_stats"]["losses"]
        
        # Save to persistent file
        save_persistent_stats()
        
        print(f"✅ Cache loaded: {cache['ranked_wins']}W/{cache['ranked_losses']}L")
    except Exception as e:
        print(f"❌ Error initializing ranked stats: {e}")

# ================== MATCH CACHE ================== #

MATCH_CACHE_FILE = "match_cache.json"

def load_match_cache(puuid=None):
    """Load cached match data with improved validation and error handling"""
    try:
        if not os.path.exists(MATCH_CACHE_FILE):
            logger.info("Match cache file does not exist, will create new one")
            return {"matches": [], "last_updated": 0, "ranked_stats": {"wins": 0, "losses": 0}, "excluded_matches": []}

        with open(MATCH_CACHE_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)

        # Validate cache structure
        if not isinstance(data, dict):
            logger.warning("Invalid cache format, resetting")
            return {"matches": [], "last_updated": 0, "ranked_stats": {"wins": 0, "losses": 0}, "excluded_matches": []}

        # Validate cache is for current PUUID
        if puuid and data.get("puuid") != puuid:
            logger.info(f"Cache PUUID mismatch: cache has {data.get('puuid')}, current is {puuid}")
            return {"matches": [], "last_updated": 0, "ranked_stats": {"wins": 0, "losses": 0}, "excluded_matches": []}

        # Ensure required fields exist
        if "matches" not in data:
            data["matches"] = []
        if "ranked_stats" not in data:
            data["ranked_stats"] = {"wins": 0, "losses": 0}
        if "excluded_matches" not in data:
            data["excluded_matches"] = []
        if "last_updated" not in data:
            data["last_updated"] = 0

        # Validate ranked_stats structure
        stats = data["ranked_stats"]
        if not isinstance(stats, dict) or "wins" not in stats or "losses" not in stats:
            logger.warning("Invalid ranked_stats in cache, resetting")
            data["ranked_stats"] = {"wins": 0, "losses": 0}

        logger.debug("Match cache loaded successfully")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Corrupted cache file: {e}, resetting")
        return {"matches": [], "last_updated": 0, "ranked_stats": {"wins": 0, "losses": 0}, "excluded_matches": []}
    except Exception as e:
        logger.error(f"Error loading match cache: {e}")
        return {"matches": [], "last_updated": 0, "ranked_stats": {"wins": 0, "losses": 0}, "excluded_matches": []}

def save_match_cache(cache_data, puuid=None):
    """Save match data to cache with error handling"""
    if puuid:
        cache_data["puuid"] = puuid

    try:
        # Create backup of existing cache
        if os.path.exists(MATCH_CACHE_FILE):
            backup_file = MATCH_CACHE_FILE + ".backup"
            os.replace(MATCH_CACHE_FILE, backup_file)

        with open(MATCH_CACHE_FILE, "w", encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)

        logger.debug("Match cache saved successfully")

    except Exception as e:
        logger.error(f"Error saving match cache: {e}")
        # Try to restore backup
        backup_file = MATCH_CACHE_FILE + ".backup"
        if os.path.exists(backup_file):
            try:
                os.replace(backup_file, MATCH_CACHE_FILE)
                logger.info("Restored cache from backup")
            except Exception as e2:
                logger.error(f"Failed to restore backup: {e2}")

def update_match_cache(puuid):
    """Update the match cache with latest data"""
    print("🔄 Updating match cache...")
    try:
        # Get all matches
        matches = get_matches(puuid, count=None)
        if not matches:
            print("⚠️ No matches to cache")
            return

        # Process all matches for ranked stats
        wins = 0
        losses = 0
        processed_matches = []

        for i, match_id in enumerate(matches):
            if i % 50 == 0 and i > 0:
                print(f"📊 Processing match {i+1}/{len(matches)}")
            match_data = get_match_data(match_id)
            if not match_data or "info" not in match_data:
                continue

            # Only ranked games
            if match_data["info"].get("queueId") != 420:
                continue

            # Find player
            player = next((p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None)
            if not player:
                continue

            # Skip remakes
            if match_data["info"]["gameDuration"] < 300:
                continue

            # Record the result
            result = "W" if player["win"] else "L"
            processed_matches.append({
                "match_id": match_id,
                "result": result,
                "timestamp": match_data["info"]["gameCreation"]
            })

            if player["win"]:
                wins += 1
            else:
                losses += 1

        # Save to cache
        cache_data = {
            "matches": processed_matches,
            "last_updated": time.time(),
            "ranked_stats": {"wins": wins, "losses": losses}
        }
        save_match_cache(cache_data, puuid)
        print(f"✅ Cache updated with {len(processed_matches)} ranked games: {wins}W/{losses}L")

    except Exception as e:
        print(f"❌ Error updating match cache: {e}")

def get_cached_stats(puuid=None):
    """Get stats from cache"""
    cache_data = load_match_cache(puuid)
    return cache_data["ranked_stats"]

# ================== CACHE ================== #

cache = {
    "games": [],
    "last_game_id": None,
    "today_date": "",
    "today_wins": 0,
    "today_losses": 0,
    "session_start": None,  # When current session started (24h window)
    "session_wins": 0,     # Wins in current session
    "session_losses": 0,   # Losses in current session
    "ranked_wins": 0,      # Total ranked wins (persistent)
    "ranked_losses": 0,    # Total ranked losses (persistent)
    "win_streak": 0,       # Current win streak (persistent)
    "lose_streak": 0,      # Current lose streak (persistent)
    "max_win_streak": 0,   # Max win streak ever
    "max_lose_streak": 0,  # Max lose streak ever
    "kda": 0,
    "winrate": 0,
    "last_game": None,
    "rank": "cargando...",
    "rank_last_update": None,
    "api_status": "checking...",
    "last_rank_check": 0  # Timestamp of last rank API call
}

# Load persistent stats on startup
persistent_stats = load_persistent_stats()
cache.update(persistent_stats)

PUUID = None

in_game = False
last_game_live_id = None

# ================== API ================== #

class RiotAPI:
    """Improved Riot API client with better rate limiting and error handling"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.last_request_time = 0
        self.request_count = 0
        self.rate_limit_reset = 0

    def _wait_for_rate_limit(self):
        """Handle rate limiting intelligently"""
        current_time = time.time()

        # Reset counter every 2 minutes
        if current_time - self.rate_limit_reset > 120:
            self.request_count = 0
            self.rate_limit_reset = current_time

        # If we've made 20 requests in 2 minutes, wait
        if self.request_count >= 20:
            wait_time = 120 - (current_time - self.rate_limit_reset)
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                time.sleep(wait_time)
                self.request_count = 0
                self.rate_limit_reset = time.time()

        # Minimum delay between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < 1.2:  # 50 requests per minute max
            time.sleep(1.2 - time_since_last)

        self.last_request_time = time.time()
        self.request_count += 1

    def make_request(self, url, max_retries=3):
        """Make API request with improved error handling and rate limiting"""
        self._wait_for_rate_limit()

        for attempt in range(max_retries):
            try:
                logger.debug(f"Making API request: {url}")
                res = requests.get(url, headers={"X-Riot-Token": self.api_key}, timeout=15)

                if res.status_code == 200:
                    logger.debug("API request successful")
                    return res.json()
                elif res.status_code == 429:  # Rate limit
                    retry_after = int(res.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited, waiting {retry_after} seconds")
                    time.sleep(min(retry_after, 120))
                    continue
                elif res.status_code == 404:  # Not found
                    if "spectator" in url:
                        logger.debug("Player not in game (expected 404)")
                        return None
                    logger.warning(f"API 404 - Resource not found: {url}")
                    return None
                elif res.status_code == 403:  # Forbidden
                    logger.error("API key expired or insufficient permissions")
                    return None
                elif res.status_code == 401:  # Unauthorized
                    logger.error("API key invalid")
                    return None
                elif res.status_code == 503:  # Service unavailable
                    logger.warning("Riot API service unavailable, retrying...")
                    time.sleep(5)
                    continue
                else:
                    logger.error(f"API error {res.status_code}: {res.text}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None

        logger.error("All API request attempts failed")
        return None

# Initialize API client
riot_api = RiotAPI(RIOT_API_KEY)

def make_api_request(url, max_retries=3):
    """Legacy function for backward compatibility"""
    return riot_api.make_request(url, max_retries)

def get_puuid():
    """Get PUUID with improved error handling"""
    try:
        url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{GAME_NAME}/{TAG_LINE}"
        data = riot_api.make_request(url)

        if data and "puuid" in data:
            cache["api_status"] = "working"
            logger.info(f"Successfully retrieved PUUID for {GAME_NAME}#{TAG_LINE}")
            return data["puuid"]
        else:
            cache["api_status"] = "API error - check key"
            logger.error("Failed to get PUUID - check API key and summoner details")
            return None
    except Exception as e:
        logger.error(f"Error getting PUUID: {e}")
        cache["api_status"] = "API error"
        return None

def get_matches(puuid, count=None):
    """Get match IDs with improved error handling and validation"""
    if not puuid:
        logger.error("No PUUID provided to get_matches")
        return []

    try:
        all_matches = []
        start = 0
        batch_size = 100

        while True:
            url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={batch_size}"
            data = riot_api.make_request(url)

            if not data:
                logger.warning("No match data received")
                break

            if not isinstance(data, list):
                logger.error(f"Invalid match data format: {type(data)}")
                break

            all_matches.extend(data)

            # If we got fewer than batch_size, we've reached the end
            if len(data) < batch_size:
                break

            start += batch_size

            # Safety limit to prevent infinite loops
            if start > 1000:
                logger.warning("Reached maximum match fetch limit (1000+ matches)")
                break

            # If count is specified and we've reached it, stop
            if count and len(all_matches) >= count:
                all_matches = all_matches[:count]
                break

        logger.debug(f"Retrieved {len(all_matches)} matches for PUUID")
        return all_matches

    except Exception as e:
        logger.error(f"Error getting matches: {e}")
        return []

def get_match_data(match_id):
    """Get match data with validation"""
    if not match_id:
        logger.error("No match_id provided")
        return None

    try:
        url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
        data = riot_api.make_request(url)

        if not data:
            return None

        # Validate required fields
        if "info" not in data or "participants" not in data["info"]:
            logger.warning(f"Invalid match data structure for match {match_id}")
            return None

        return data

    except Exception as e:
        logger.error(f"Error getting match data for {match_id}: {e}")
        return None

def get_rank(puuid):
    url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    data = make_api_request(url)
    return data if data else []

def get_spectator_data(puuid):
    """Get current game spectator data with improved error handling"""
    if not puuid:
        logger.error("No PUUID provided to get_spectator_data")
        return None

    try:
        url = f"https://euw1.api.riotgames.com/lol/spectator/v5/active-games/by-puuid/{puuid}"
        data = riot_api.make_request(url)

        # If data is None, it means either error or not in game
        # The make_request function already handles 404 as None for spectator API
        if data is None:
            logger.debug("Player not in game or spectator API unavailable")
            cache["api_status"] = "working - player not in game"
            return None

        # Validate spectator data structure
        required_fields = ["gameId", "participants", "gameQueueConfigId"]
        if not all(field in data for field in required_fields):
            logger.warning("Invalid spectator data structure")
            return None

        return data

    except Exception as e:
        logger.error(f"Error getting spectator data: {e}")
        cache["api_status"] = "spectator API error"
        return None

# ================== IRELIA RECIENTE ================== #

def calcular_irelia_reciente(puuid):
    matches = get_matches(puuid, count=30)

    wins = games = k = d = a = 0

    for match_id in matches:
        data = get_match_data(match_id)

        if "info" not in data or data["info"]["gameDuration"] < 300:
            continue

        for p in data["info"]["participants"]:
            if p["puuid"] == puuid and p["championName"] == "Irelia":
                games += 1
                wins += int(p["win"])
                k += p["kills"]
                d += p["deaths"]
                a += p["assists"]

    if games == 0:
        return None

    return {
        "wr": int((wins / games) * 100),
        "kda": round((k + a) / d, 2) if d else k + a
    }
                
# ================= GAME CHECK ================= #
async def actualizar_datos(bot):
    global PUUID, in_game, last_game_live_id

    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            if PUUID is None:
                PUUID = get_puuid()
                if PUUID is None:
                    logger.warning("Cannot get PUUID - API key issue, retrying in 60 seconds")
                    await asyncio.sleep(60)
                    continue

                # Initialize ranked stats on first PUUID acquisition
                initialize_ranked_stats(PUUID)

            puuid = PUUID

            # Check if in game (spectator API - may not be available)
            game_data = get_spectator_data(puuid)

            if game_data is None:
                logger.info("Spectator API unavailable or player not in game")
                game_data = False  # Treat as not in game

            logger.debug(f"Game status: {'IN GAME' if game_data else 'NOT IN GAME'}")

            # ================= IN GAME ================= #
            if game_data:
                current_game_id = game_data.get("gameId")
                if not current_game_id:
                    await asyncio.sleep(5)
                    continue

                queue_id = game_data.get("gameQueueConfigId", 0)

                print("🎮 IN GAME | ID:", current_game_id, "| QUEUE:", queue_id)

                if queue_id == 420:
                    tipo = "RANKED 🏆"
                elif queue_id == 450:
                    tipo = "ARAM 🎲"
                elif queue_id == 440:
                    tipo = "FLEX 🧩"
                elif queue_id in [1700, 1710, 1720]:
                    tipo = "ARENA ⚔️"
                else:
                    tipo = "NORMAL 🎮"

                # 🔥 START
                if current_game_id != last_game_live_id:
                    print("🚀 START DETECTADO")

                    in_game = True
                    last_game_live_id = current_game_id

                    aliados = []
                    enemigos = []
                    team_id = None

                    for p in game_data["participants"]:
                        if p.get("puuid") == puuid:
                            team_id = p["teamId"]

                    for p in game_data["participants"]:
                        champ_id = p.get("championId")
                        champ = champions.get(champ_id, str(champ_id))

                        if p["teamId"] == team_id:
                            aliados.append(champ)
                        else:
                            enemigos.append(champ)

                    msg = f"🎮 START ({tipo})\n🟦 {' '.join(aliados)}\n🟥 {' '.join(enemigos)}"
                    await bot.connected_channels[0].send(msg)

            # ================= NO GAME ================= #
            else:
                print("❌ NO GAME DETECTED")

                # 🔥 END (CORRECTO)
                # 🔥 END (CORRECTO)
                if in_game:
                    print("🏁 END DETECTADO")

                    in_game = False
                    last_game_live_id = None

                    await asyncio.sleep(10)

                    matches = get_matches(puuid, 1)

                    if matches:
                        last_id = matches[0]
                        data = get_match_data(last_id)

                        if data and "info" in data:
                            player = next(
                                (p for p in data["info"]["participants"] if p["puuid"] == puuid),
                                None
                            )

                            if player:
                                k = player["kills"]
                                d = player["deaths"]
                                a = player["assists"]
                                champ = player["championName"]

                                resultado_tipo = cache.get("resultado_tipo", "UNKNOWN")
    
                                if resultado_tipo == "WIN":
                                    result = "WIN 🔥"
                                elif resultado_tipo == "LOSS":
                                    result = "LOSE 💀"
                                elif resultado_tipo == "MITIGATED":
                                    result = "LOSS MITIGATED 🛡️"
                                elif resultado_tipo == "REMAKE":
                                    result = "REMAKE ⏱️"
                                else:
                                    result = "Partida terminada"

                                print("📊 RESULT:", champ, k, d, a, result)

                                msg = f"🏁 {champ} {k}/{d}/{a} {result}"
                                await bot.connected_channels[0].send(msg)

                            else:
                                await bot.connected_channels[0].send("🏁 Partida terminada")
                        else:
                            print("⚠️ Datos inválidos de partida")
                    else:
                        await bot.connected_channels[0].send("🏁 Partida terminada")
            # ==============RANK UPDATE ================= #
            # Update rank periodically regardless of game status
            now = time.time()
            if now - cache["last_rank_check"] > 300:  # 5 minutes
                ranked = get_rank(puuid) or []
                if ranked:
                    old_rank = cache["rank"]
                    cache["rank"] = format_rank(ranked)
                    cache["rank_last_update"] = datetime.now()
                    cache["api_status"] = "working"
                    cache["last_rank_check"] = now
                    if old_rank != cache["rank"]:
                        print(f"✅ Rank updated: {cache['rank']}")
                    else:
                        print("✅ Rank checked (no change)")
                else:
                    cache["api_status"] = "API error - check key"
                    cache["last_rank_check"] = now

            matches = get_matches(puuid, 1) or []
            if not matches or not isinstance(matches, list):
                await asyncio.sleep(30)
                continue

            last_id = matches[0]
            data = get_match_data(last_id)
            if not data or "info" not in data:
                await asyncio.sleep(30)
                continue
            
            # 🧠 PRIMERA EJECUCIÓN (NO CONTAR)
            if cache["last_game_id"] is None:
                cache["last_game_id"] = last_id
                print("ℹ️  First run - skipping this match to avoid spam")
                continue
            
            # 🔥 ANTI SPAM - Skip if same match
            if last_id == cache["last_game_id"]:
                # Same match still being processed, sleep and try again
                await asyncio.sleep(SLEEP_OUT_GAME)
                continue

            # 🎉 NEW MATCH DETECTED!
            print(f"🎉 NEW MATCH DETECTED: {last_id}")

            # ---- IRELIA ----
            data_guardada = cargar_datos()

            if last_id != data_guardada.get("last_match_id", ""):

                if data["info"]["gameDuration"] >= 300:
                    for p in data["info"]["participants"]:
                        if p["puuid"] == puuid and p["championName"] == "Irelia":
                            data_guardada["games"] += 1
                            data_guardada["wins"] += int(p["win"])

                data_guardada["last_match_id"] = last_id
                guardar_datos(data_guardada)

            # ---- GENERAL ----

            queue_id = data["info"]["queueId"]

            # Get game type
            if queue_id == 420:
                game_type = "⭐ RANKED 🏆"
            elif queue_id == 440:
                game_type = "🧩 FLEX 5V5"
            elif queue_id == 450:
                game_type = "🎲 ARAM 🎪"
            elif queue_id in [1700, 1710, 1720]:
                game_type = "⚔️ ARENA 🗡️"
            elif queue_id in [400, 430]:
                game_type = "🎮 NORMAL 🎯"
            else:
                game_type = f"❓ GAME #{queue_id}"

            player = next((p for p in data["info"]["participants"] if p["puuid"] == puuid), None)
            if not player:
                cache["last_game_id"] = last_id
                continue

            win = player["win"]
            k, d, a = player["kills"], player["deaths"], player["assists"]
            champ = player["championName"]

            # ================= TIPO DE PARTIDA ================= #
            duracion = data["info"]["gameDuration"]

            remake = duracion < 300
            afk_detectado = False

            team_players = [
                p for p in data["info"]["participants"]
                if p["teamId"] == player["teamId"] and p["puuid"] != puuid
            ]

            if len(team_players) > 0:
                avg_gold = sum(p["goldEarned"] for p in team_players) / len(team_players)
                avg_damage = sum(p["totalDamageDealtToChampions"] for p in team_players) / len(team_players)
                avg_level = sum(p["champLevel"] for p in team_players) / len(team_players)

                for p in team_players:
                    if p["timePlayed"] < (duracion * 0.5):
                        afk_detectado = True
                        break

                    condiciones = 0

                    if p["goldEarned"] < (avg_gold * 0.35):
                        condiciones += 1
                    if p["totalDamageDealtToChampions"] < (avg_damage * 0.20):
                        condiciones += 1
                    if p["champLevel"] < (avg_level - 4):
                        condiciones += 1

                    if condiciones >= 2:
                        afk_detectado = True
                        break

            if remake:
                resultado_tipo = "REMAKE"
            elif afk_detectado and not win:
                resultado_tipo = "MITIGATED"
            elif win:
                resultado_tipo = "WIN"
            else:
                resultado_tipo = "LOSS"

            cache["resultado_tipo"] = resultado_tipo

            # TEXTO
            if resultado_tipo == "WIN":
                texto = "✅ WIN 🔥🔥🔥"
            elif resultado_tipo == "LOSS":
                texto = "❌ LOSE 💀"
            elif resultado_tipo == "MITIGATED":
                texto = "🛡️ LOSS MITIGATED"
            else:
                texto = "⏱️ REMAKE"

            cache["last_game"] = f"{champ} {k}/{d}/{a} {texto}"

            # 🔥 SEND END GAME MESSAGE FOR ALL GAME TYPES 🔥
            try:
                # Build enhanced message with detailed stats like LouisGameDev's bot
                detailed_msg = format_detailed_game_stats(player, data, game_type)
                await bot.connected_channels[0].send(detailed_msg)
                print(f"✅ SENT DETAILED GAME END MESSAGE: {detailed_msg}")
            except Exception as e:
                print(f"❌ Error sending detailed message: {e}")
                # Fallback to simple message
                try:
                    msg = f"🏁 [{game_type}] {champ.upper()} | K/D/A: {k}/{d}/{a} | {texto}"
                    await bot.connected_channels[0].send(msg)
                    print(f"✅ SENT FALLBACK GAME END MESSAGE: {msg}")
                except Exception as e2:
                    print(f"❌ Error sending fallback message: {e2}")

            # Only update daily stats for ranked games
            if queue_id != 420:
                print(f"ℹ️  {game_type} game detected (not ranked) - message sent!")
                cache["last_game_id"] = last_id
                await asyncio.sleep(SLEEP_OUT_GAME)
                continue

            print(f"ℹ️  Ranked game detected - updating stats...")

            # HISTORIAL
            if resultado_tipo == "WIN":
                cache["games"].insert(0, "W")
            elif resultado_tipo == "LOSS":
                cache["games"].insert(0, "L")

            cache["games"] = cache["games"][:5]

            # FECHA Y SESIÓN (24H)
            zona = pytz.timezone("Europe/Madrid")
            ahora = datetime.now(zona)
            hoy = ahora.date()

            # Reset daily counters
            if cache["today_date"] == "":
                cache["today_date"] = str(hoy)

            if str(hoy) != cache["today_date"]:
                cache["today_date"] = str(hoy)
                cache["today_wins"] = 0
                cache["today_losses"] = 0

            # Session tracking (24h window)
            if cache["session_start"] is None:
                cache["session_start"] = ahora.timestamp()

            # Reset session if 24h have passed
            if ahora.timestamp() - cache["session_start"] >= 86400:  # 24 hours
                cache["session_start"] = ahora.timestamp()
                cache["session_wins"] = 0
                cache["session_losses"] = 0

            # ================= CONTADOR ================= #
            if resultado_tipo == "WIN":
                # Daily stats
                cache["today_wins"] += 1
                # Session stats
                cache["session_wins"] += 1
                # Ranked stats (only for ranked games)
                if queue_id == 420:  # RANKED_SOLO_5x5
                    cache["ranked_wins"] += 1

                # Streak handling
                old_lose_streak = cache["lose_streak"]
                cache["win_streak"] += 1
                cache["lose_streak"] = 0

                # Check for lose streak break
                if old_lose_streak >= 2:
                    try:
                        msg = f"🔥 Lose streak of {old_lose_streak} broken! 🔥"
                        await bot.connected_channels[0].send(msg)
                        print(f"✅ SENT STREAK BREAK MESSAGE: {msg}")
                    except Exception as e:
                        print(f"❌ Error sending streak break message: {e}")

                # Update max win streak
                if cache["win_streak"] > cache["max_win_streak"]:
                    cache["max_win_streak"] = cache["win_streak"]

            elif resultado_tipo == "LOSS":
                # Daily stats
                cache["today_losses"] += 1
                # Session stats
                cache["session_losses"] += 1
                # Ranked stats (only for ranked games)
                if queue_id == 420:  # RANKED_SOLO_5x5
                    cache["ranked_losses"] += 1

                # Streak handling
                old_win_streak = cache["win_streak"]
                cache["lose_streak"] += 1
                cache["win_streak"] = 0

                # Check for win streak break
                if old_win_streak >= 2:
                    try:
                        msg = f"💀 Win streak of {old_win_streak} broken! 💀"
                        await bot.connected_channels[0].send(msg)
                        print(f"✅ SENT STREAK BREAK MESSAGE: {msg}")
                    except Exception as e:
                        print(f"❌ Error sending streak break message: {e}")

                # Update max lose streak
                if cache["lose_streak"] > cache["max_lose_streak"]:
                    cache["max_lose_streak"] = cache["lose_streak"]

            # KDA
            cache["kda"] = round((k + a) / d, 2) if d else k + a

            # WR (Session-based)
            total_session = cache["session_wins"] + cache["session_losses"]
            if total_session:
                cache["winrate"] = int((cache["session_wins"] / total_session) * 100)

            # ANTI DUPLICADOS (CLAVE)
            cache["last_game_id"] = last_id

            # Save persistent stats after each game
            save_persistent_stats()


            # ================= WINS ================= #
            if cache["win_streak"] >= 3:
                msg = None
                ws = cache["win_streak"]

                if ws == 3: msg = "🔥 ON FIRE (3W)"
                elif ws == 4: msg = "🔥 4 WINS SEGUIDAS"
                elif ws == 5: msg = "🔥 5 WINS WTF"
                elif ws == 6: msg = "🔥 6 WINS (IMPARABLE)"
                elif ws == 7: msg = "🔥 7 WINS (SMURF DETECTED)"
                elif ws == 8: msg = "🔥 8 WINS (MONSTRUO)"
                elif ws == 9: msg = "🔥 9 WINS (INHUMANO)"
                elif ws == 10: msg = "🔥 10 WINS (DIOS)"
                elif ws == 11: msg = "🔥 11 WINS (NO FALLA)"
                elif ws == 12: msg = "🔥 12 WINS (MODO DIABLO)"
                elif ws == 13: msg = "🔥 13 WINS (ESTÁ ROTO)"
                elif ws == 14: msg = "🔥 14 WINS (NO ES NORMAL)"
                elif ws == 15: msg = "🔥 15 WINS (DESTRUIDO)"
                elif ws == 16: msg = "🔥 16 WINS (LOBBY DIFF)"
                elif ws == 17: msg = "🔥 17 WINS (SIN SENTIDO)"
                elif ws == 18: msg = "🔥 18 WINS (HACK?)"
                elif ws == 19: msg = "🔥 19 WINS (ESTO ES ILEGAL)"
                elif ws >= 20: msg = f"🔥 {ws} WINS SEGUIDAS (LEYENDA)"

                if msg:
                    await bot.connected_channels[0].send(msg)

            # ================= LOSSES ================= #
            if cache["lose_streak"] >= 2:
                msg = None
                ls = cache["lose_streak"]

                if ls == 2:
                    msg = "💀 TILT ALERT"
                elif ls == 3:
                    msg = "💀 3 LOSSES... cuidado"
                elif ls == 4:
                    msg = "💀 4 LOSSES... FF mental"
                elif ls == 5:
                    msg = "💀 5 LOSSES... desastre"
                elif ls == 6:
                    msg = "💀 6 LOSSES... se acabó"
                elif ls == 7:
                    msg = "💀 7 LOSSES... no es tu día"
                elif ls >= 8:
                    msg = f"💀 {ls} LOSSES... APAGA Y VETE"

                if msg:
                    await bot.connected_channels[0].send(msg)

        except Exception as e:
            consecutive_errors += 1
            logger.error(f"💥 ERROR GENERAL (#{consecutive_errors}): {e}")

            if consecutive_errors >= max_consecutive_errors:
                logger.critical(f"Too many consecutive errors ({consecutive_errors}), restarting in 5 minutes")
                await asyncio.sleep(300)  # 5 minutes
                consecutive_errors = 0
            else:
                await asyncio.sleep(30)  # Shorter wait for transient errors

        if in_game:
            await asyncio.sleep(SLEEP_IN_GAME)
        else:
            await asyncio.sleep(SLEEP_OUT_GAME)
# ================== BOT ================== #

class Bot(commands.Bot):

    def __init__(self):
        super().__init__(token=TWITCH_TOKEN, prefix="!", initial_channels=[CHANNEL])

    async def event_ready(self):
        print(f'Bot conectado como {self.nick}')
        self.loop.create_task(actualizar_datos(self))

    @commands.command()
    async def hora(self, ctx):
        if not can_use(ctx.author.name, "hora"): return
        zona = pytz.timezone("Europe/Madrid")
        await ctx.send(datetime.now(zona).strftime("Hora: %H:%M:%S"))

    @commands.command()
    async def rank(self, ctx):
        if not can_use(ctx.author.name, "rank"): return

        rank_info = cache["rank"]
        if cache["rank_last_update"]:
            # Show how fresh the data is
            time_diff = datetime.now() - cache["rank_last_update"]
            minutes_ago = int(time_diff.total_seconds() / 60)
            if minutes_ago < 1:
                freshness = " (just updated)"
            elif minutes_ago == 1:
                freshness = " (1 min ago)"
            else:
                freshness = f" ({minutes_ago} mins ago)"
            rank_info += freshness

        await ctx.send(rank_info)

    @commands.command()
    async def apistatus(self, ctx):
        if not can_use(ctx.author.name, "apistatus"): return
        if not has_permission(ctx, owner_only=True): await ctx.send("❌ Permission denied"); return
        status = cache["api_status"]
        await ctx.send(f"API Status: {status}")

    @commands.command()
    async def rankrefresh(self, ctx):
        if not can_use(ctx.author.name, "rankrefresh"): return
        if not has_permission(ctx, owner_only=False): await ctx.send("❌ Permission denied"); return

        # Manual rank refresh
        if PUUID:
            ranked = get_rank(PUUID) or []
            if ranked:
                cache["rank"] = format_rank(ranked)
                cache["rank_last_update"] = datetime.now()
                cache["api_status"] = "working"
                await ctx.send(f"✅ Rank updated: {cache['rank']}")
            else:
                await ctx.send("❌ Failed to refresh rank - check API status")
        else:
            await ctx.send("❌ Cannot refresh - PUUID not available")

    @commands.command()
    async def clearcache(self, ctx):
        if not can_use(ctx.author.name, "clearcache"): return
        if not has_permission(ctx, owner_only=False): await ctx.send("❌ Permission denied"); return
        
        try:
            import os
            if os.path.exists(MATCH_CACHE_FILE):
                os.remove(MATCH_CACHE_FILE)
                await ctx.send("🗑️ Cache cleared! Use !refresh to rebuild it.")
            else:
                await ctx.send("📁 No cache file found.")
        except Exception as e:
            await ctx.send(f"❌ Error clearing cache: {str(e)}")

    @commands.command()
    async def refresh(self, ctx):
        if not can_use(ctx.author.name, "refresh"): return
        if not has_permission(ctx, owner_only=False): await ctx.send("❌ Permission denied"); return
        
        if not PUUID:
            await ctx.send("❌ Cannot refresh - PUUID not available")
            return
        
        await ctx.send("🔄 Refreshing match cache... This may take a while.")
        
        # Run in background to avoid blocking
        import asyncio
        asyncio.create_task(refresh_cache_async(ctx, PUUID))

    async def refresh_cache_async(ctx, puuid):
        try:
            update_match_cache(puuid)
            cache_data = load_match_cache(puuid)
            stats = cache_data["ranked_stats"]
            await ctx.send(f"✅ Cache refreshed! Current stats: {stats['wins']}W/{stats['losses']}L")
        except Exception as e:
            await ctx.send(f"❌ Error refreshing cache: {str(e)}")

    @commands.command()
    async def updatekey(self, ctx, new_key: str = None):
        """Update API key - usage: !updatekey RGAPI-xxxxx"""
        if ctx.author.name.lower() not in ["ruben_irpg", "your_twitch_username"]:  # Only allow bot owner
            await ctx.send("❌ Only bot owner can update API key")
            return

        if not new_key or not new_key.startswith("RGAPI-"):
            await ctx.send("❌ Invalid key format. Use: !updatekey RGAPI-xxxxx")
            return

        try:
            # Update config file
            config.set('RIOT', 'api_key', new_key)
            with open(config_file, 'w') as f:
                config.write(f)

            # Update runtime variable
            global RIOT_API_KEY, riot_api
            RIOT_API_KEY = new_key
            riot_api = RiotAPI(RIOT_API_KEY)

            # Test the new key
            test_puuid = get_puuid()
            if test_puuid:
                global PUUID
                PUUID = test_puuid  # Update PUUID with new key
                await ctx.send("✅ API key updated and working!")
                logger.info("API key updated successfully")
            else:
                await ctx.send("❌ API key updated but not working - check the key")
                logger.warning("API key updated but validation failed")

        except Exception as e:
            await ctx.send(f"❌ Error updating API key: {str(e)}")
            logger.error(f"Error updating API key: {e}")

    @commands.command()
    async def health(self, ctx):
        """Check bot health and API status"""
        if not can_use(ctx.author.name, "health"): return
        if not has_permission(ctx, owner_only=False): await ctx.send("❌ Permission denied"); return

        health_status = {
            "puuid": "✅ Available" if PUUID else "❌ Missing",
            "api_status": cache.get("api_status", "unknown"),
            "cache_loaded": "✅ Yes" if os.path.exists(MATCH_CACHE_FILE) else "❌ No",
            "config_loaded": "✅ Yes" if os.path.exists(config_file) else "❌ No",
            "last_rank_update": cache.get("rank_last_update", "Never"),
            "uptime": "Bot running"
        }

        response = "🤖 Bot Health Check:\n" + "\n".join(f"• {k}: {v}" for k, v in health_status.items())
        await ctx.send(response)

    @commands.command()
    async def irelia(self, ctx):
        if not can_use(ctx.author.name, "irelia"): return
        puuid = get_puuid()
        reciente = calcular_irelia_reciente(puuid)
        total = cargar_datos()

        if not reciente:
            await ctx.send("No hay partidas recientes de Irelia")
            return

        await ctx.send(
            f"⚔️ Irelia: {reciente['wr']}% WR | KDA {reciente['kda']} ({total['games']} games | {total['wins']}W)"
        )

    @commands.command(aliases=["lastgame", "ult"])
    async def last(self, ctx):
        if not can_use(ctx.author.name, "last"): return
        if cache["last_game"]:
            await ctx.send(f"Last game: {cache['last_game']}")
        else:
            await ctx.send("No last game data available")

    @commands.command(aliases=["todaystats", "hoy", "sesion"])
    async def today(self, ctx):
        if not can_use(ctx.author.name, "today"): return
        
        if not PUUID:
            await ctx.send("❌ Cannot calculate - PUUID not available")
            return
        
        # Get stats for last 24 hours from API
        stats = calculate_stats_from_api(PUUID, hours=24)
        total = stats["wins"] + stats["losses"]
        
        if total == 0:
            await ctx.send("📅 Today (24h): No ranked games")
        else:
            wr = int((stats["wins"] / total) * 100)
            
            # Create visual representation: 🟦 for wins, 🟥 for losses
            # Reverse the games list to show chronological order (oldest to newest)
            visual_games = []
            for game in reversed(stats["games"]):
                if game == "W":
                    visual_games.append("🟦")
                elif game == "L":
                    visual_games.append("🟥")
            
            visual_str = "".join(visual_games)
            
            await ctx.send(f"📅 Today (24h): {stats['wins']}W/{stats['losses']}L Winrate {wr}% {visual_str}")

    @commands.command(aliases=["victorias", "w"])
    async def wins(self, ctx):
        if not can_use(ctx.author.name, "wins"): return
        
        if not PUUID:
            await ctx.send("❌ Cannot calculate - PUUID not available")
            return
        
        # Get today's ranked wins from API (last 24 hours)
        stats = calculate_stats_from_api(PUUID, hours=24)
        await ctx.send(f"🏆 Today's Ranked Wins: {stats['wins']}")

    @commands.command(aliases=["derrotas", "l"])
    async def losses(self, ctx):
        if not can_use(ctx.author.name, "losses"): return
        
        if not PUUID:
            await ctx.send("❌ Cannot calculate - PUUID not available")
            return
        
        # Get today's ranked losses from API (last 24 hours)
        stats = calculate_stats_from_api(PUUID, hours=24)
        await ctx.send(f"💀 Today's Ranked Losses: {stats['losses']}")

    @commands.command(aliases=["help"])
    async def cmd(self, ctx):
        if not can_use(ctx.author.name, "cmd"): return
        help_text = """
🎮 Bot Commands:
!hora - Show current time
!rank - Show current League rank
!apistatus - Check API status (owner only)
!rankrefresh - Manually refresh rank (owner only and mods)
!clearcache - Clear match cache (owner only and mods)
!refresh - Rebuild match cache from API (owner only and mods)
!updatekey <key> - Update Riot API key (owner only)
!health - Check bot health and status (owner only and mods)
!irelia - Show Irelia stats
!last (aliases: !lastgame, !ult) - Show last game result
!today (aliases: !sesion, !todaystats, !hoy) - Show session stats (24h) with visual history
!wins (aliases: !victorias, !w) - Show today's ranked wins (24h)
!losses (aliases: !derrotas, !l) - Show today's ranked losses (24h)
!cmd (!help) - List all commands (help)
!kda (aliases: !kd, !stats) - Show average KDA from last 15 ranked games
!winrate (aliases: !wr) - Show winrate from last 15 ranked games
!tilt (aliases: !tilted, !tilteado) - Check lose streak
!winstreak (aliases: !streak, !racha) - Show current win streak
!historial (aliases: !history, !games) - Show recent games
!clearlose - Remove most recent loss from today's stats (owner only and mods)
!setstreak <number> - Manually set win streak (owner only and mods)

🔥 Automatic Game End Messages:
Bot automatically posts detailed game results with K/D/A, Kill Participation, damage, CS/min, gold/min, and more - just like LouisGameDev's bot!
        """.strip()
        await ctx.send(help_text)

    @commands.command(aliases=["kd", "stats"])
    async def kda(self, ctx):
        if not can_use(ctx.author.name, "kda"): return
        
        if not PUUID:
            await ctx.send("❌ Cannot calculate - PUUID not available")
            return
        
        # Calculate from last 15 ranked games
        stats = calculate_recent_ranked_stats(PUUID, num_games=15)
        
        if stats["games_analyzed"] == 0:
            await ctx.send("❌ No recent ranked games found")
        else:
            await ctx.send(f"KDA: {stats['kda']} (Last {stats['games_analyzed']} ranked games)")

    @commands.command(aliases=["wr"])
    async def winrate(self, ctx):
        if not can_use(ctx.author.name, "winrate"): return
        
        if not PUUID:
            await ctx.send("❌ Cannot calculate - PUUID not available")
            return
        
        # Calculate from last 15 ranked games
        stats = calculate_recent_ranked_stats(PUUID, num_games=15)
        
        if stats["games_analyzed"] == 0:
            await ctx.send("❌ No recent ranked games found")
        else:
            await ctx.send(f"WR: {stats['winrate']}% (Last {stats['games_analyzed']} ranked games)")

    @commands.command(aliases=["tilted", "tilteado"])
    async def tilt(self, ctx):
        if not can_use(ctx.author.name, "tilt"): return
        
        if not PUUID:
            await ctx.send("❌ Cannot calculate - PUUID not available")
            return
        
        # Recalculate streak from API
        streak_data = calculate_streak_from_api(PUUID)
        cache["lose_streak"] = streak_data["lose_streak"]
        
        # Update max lose streak
        if cache["lose_streak"] > cache["max_lose_streak"]:
            cache["max_lose_streak"] = cache["lose_streak"]
            save_persistent_stats()
        
        if cache["lose_streak"] >= 2:
            await ctx.send(f"💀 {cache['lose_streak']} loss streak! (Max: {cache['max_lose_streak']})")
        else:
            await ctx.send("Chill 😎")

    @commands.command(aliases=["streak", "racha"])
    async def winstreak(self, ctx):
        if not can_use(ctx.author.name, "winstreak"): return
        
        if not PUUID:
            await ctx.send("❌ Cannot calculate - PUUID not available")
            return
        
        # Recalculate streak from API
        streak_data = calculate_streak_from_api(PUUID)
        cache["win_streak"] = streak_data["win_streak"]
        cache["lose_streak"] = streak_data["lose_streak"]
        
        # Update max win streak
        if cache["win_streak"] > cache["max_win_streak"]:
            cache["max_win_streak"] = cache["win_streak"]
            save_persistent_stats()
        
        if cache["win_streak"] > 0:
            await ctx.send(f"🔥 {cache['win_streak']} win streak! (Max: {cache['max_win_streak']})")
        elif cache["lose_streak"] > 0:
            await ctx.send(f"💀 {cache['lose_streak']} lose streak! (Max: {cache['max_lose_streak']})")
        else:
            await ctx.send("No active streak")

    @commands.command(aliases=["history", "games"])
    async def historial(self, ctx):
        if not can_use(ctx.author.name, "historial"): return
        await ctx.send(" - ".join(cache["games"]) or "Sin historial")

    @commands.command()
    async def clearlose(self, ctx):
        if not can_use(ctx.author.name, "clearlose"): return
        if not has_permission(ctx, owner_only=False): await ctx.send("❌ Permission denied"); return
        
        if not PUUID:
            await ctx.send("❌ Cannot clear loss - PUUID not available")
            return
        
        try:
            # Get recent matches to find the last loss
            matches = get_matches(PUUID, count=20)  # Get last 20 matches
            if not matches:
                await ctx.send("❌ No recent matches found")
                return
            
            # Load current cache
            cache_data = load_match_cache(PUUID)
            excluded_matches = set(cache_data.get("excluded_matches", []))
            
            # Find the most recent loss that isn't already excluded
            last_loss_match = None
            for match_id in matches:
                if match_id in excluded_matches:
                    continue
                    
                match_data = get_match_data(match_id)
                if not match_data or "info" not in match_data:
                    continue
                
                # Only ranked games
                if match_data["info"].get("queueId") != 420:
                    continue
                
                # Check if within 24 hours
                match_time = datetime.fromtimestamp(match_data["info"]["gameCreation"] / 1000, tz=pytz.timezone("UTC"))
                cutoff_time = datetime.now(pytz.timezone("UTC")) - timedelta(hours=24)
                if match_time < cutoff_time:
                    break  # No more recent matches
                
                # Skip remakes
                if match_data["info"]["gameDuration"] < 300:
                    continue
                
                # Find player
                player = next((p for p in match_data["info"]["participants"] if p["puuid"] == PUUID), None)
                if not player:
                    continue
                
                # Check if it's a loss
                if not player["win"]:
                    last_loss_match = match_id
                    break  # Found the most recent loss
            
            if not last_loss_match:
                await ctx.send("❌ No recent losses found to clear")
                return
            
            # Add to excluded matches
            excluded_matches.add(last_loss_match)
            cache_data["excluded_matches"] = list(excluded_matches)
            save_match_cache(cache_data, PUUID)
            
            await ctx.send(f"✅ Cleared most recent loss (match {last_loss_match[:10]}...)")
            
        except Exception as e:
            await ctx.send(f"❌ Error clearing loss: {str(e)}")

    @commands.command()
    async def setstreak(self, ctx, new_streak: int = None):
        if not can_use(ctx.author.name, "setstreak"): return
        if not has_permission(ctx, owner_only=False): await ctx.send("❌ Permission denied"); return
        
        if new_streak is None:
            await ctx.send("❌ Usage: !setstreak <number> (e.g. !setstreak 5)")
            return
        
        if new_streak < 0:
            await ctx.send("❌ Streak cannot be negative")
            return
        
        try:
            # Set the win streak
            cache["win_streak"] = new_streak
            cache["lose_streak"] = 0  # Reset lose streak when manually setting win streak
            
            # Save to persistent stats
            save_persistent_stats()
            
            await ctx.send(f"✅ Win streak set to {new_streak}")
            
        except Exception as e:
            await ctx.send(f"❌ Error setting streak: {str(e)}")

# ================== RUN ================== #

async def main():
    bot = Bot()
    await bot.start()

asyncio.run(main())
