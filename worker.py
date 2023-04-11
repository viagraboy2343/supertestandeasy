import discord
from discord.ext import commands, tasks
import random
import sqlite3
import json
import asyncio
import os

def init_database():
    conn = sqlite3.connect("discord_bot.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS data (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    conn.commit()
    return conn

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    global worlds, characters, villages, conn

    conn = init_database()
    c = conn.cursor()

    c.execute("SELECT key, value FROM data")
    data = c.fetchall()

    for key, value in data:
        print(f"Loading data: {key}, {value}")
        if key == "worlds":
            worlds = {int(k): v for k, v in json.loads(value).items()}  # Convert keys to integers
        elif key == "characters":
            characters = {int(k): v for k, v in json.loads(value).items()}  # Convert keys to integers
        elif key == "villages":
            villages = {int(k): v for k, v in json.loads(value).items()}  # Convert keys to integers (only for outer keys)

    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("------")
    age_increment_task.start()
    actions_reset_task.start()
    death_check_task.start()
    
worlds = {}
characters = {}
villages = {}
conn = None

def save_data(conn, key, value):
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO data (key, value) VALUES (?, ?)", (str(key), json.dumps(value)))  # Convert key to str
    conn.commit()

@bot.command()
async def create_world(ctx, name: str):
    if ctx.guild.id in worlds:
        await ctx.send("A world already exists in this server!")
        return

    world = {
        "name": name,
        "hectares": 50,
        "trees": [random.randint(1000, 2500) for _ in range(50)]
    }

    worlds[ctx.guild.id] = world
    await ctx.send(f"World '{name}' created with 50 hectares, each with a random range of 1000-2500 trees!")

@bot.command()
async def create_character(ctx, name: str):
    if ctx.guild.id not in worlds:
        await ctx.send("A world must be created in this server before creating a character!")
        return

    if ctx.author.id in characters:
        await ctx.send("You already have a character!")
        return

    character = {
        "name": name,
        "health": 100,
        "age": 18,
        "inventory": {"stones": 0},
        "actions": 16,
        "stonelevel": 1,
        "PStoning": 0,
        "StoningXP": 0
    }

    characters[ctx.author.id] = character
    await ctx.send(f"Character '{name}' created with 100 health, 18 years, an empty inventory, and 16 actions per day!")

try:
    conn = init_database()
except Exception as e:
    print(f"Error initializing database: {e}")

@bot.command()
async def char(ctx):
    if ctx.author.id not in characters:
        await ctx.send("You don't have a character!")
        return

    character = characters[ctx.author.id]
    stats = (
        f"Name: {character['name']}\n"
        f"Health: {character['health']}\n"
        f"Age: {character['age']}\n"
        f"Actions: {character['actions']}"
    )
    await ctx.send(f"Your character's stats:\n```\n{stats}\n```")

@bot.command()
async def inventory(ctx):
    if ctx.author.id not in characters:
        await ctx.send("You don't have a character!")
        return

    character = characters[ctx.author.id]
    if not character['inventory']:
        await ctx.send("Your inventory is empty.")
    else:
        inventory_list = "\n".join([f"{key}: {value}" for key, value in character['inventory'].items()])
        await ctx.send(f"Your inventory:\n```\n{inventory_list}\n```")

@bot.command()
async def collect_stone(ctx):
    if ctx.author.id not in characters:
        await ctx.send("You don't have a character!")
        return

    character = characters[ctx.author.id]

    if character['actions'] < 1:
        await ctx.send("You don't have enough actions!")
        return

    # Check if inventory is full
    if sum(character['inventory'].values()) >= 5:
        await ctx.send("Your inventory is full!")
        return

    # Update inventory and character stats
    stones_collected = character['stonelevel']
    character['inventory']['stones'] = character['inventory'].get('stones', 0) + stones_collected
    character['PStoning'] += 0.01
    character['StoningXP'] += 1
    character['actions'] -= 1

    # Check if Stoning XP is enough toing XP if necessary
    if character['StoningXP'] >= 100 * (1.5 ** (character['stonelevel'] - 1)):
        character['stonelevel'] += 1
        character['StoningXP'] = 0
        await ctx.send(f"Your stonelevel just got better!")
        
    await ctx.send(f"You collected {stones_collected} stones, gained {character['stonelevel'] * 0.001} PStoning points, and 1 Stoning XP!")
    

@bot.command()
async def create_village(ctx, name: str):
    if ctx.guild.id not in worlds:
        await ctx.send("A world must be created in this server before creating a village!")
        return

    if ctx.author.id not in characters:
        await ctx.send("You must create a character before creating a village!")
        return

    if ctx.guild.id not in villages:
        villages[ctx.guild.id] = {}

    if name in villages[ctx.guild.id]:
        await ctx.send("A village with this name already exists in this server!")
        return

    village = {
        "name": name,
        "members": [ctx.author.id],
        "technologies": [],
        "reflect_attempts": 0
    }

    villages[ctx.guild.id][name] = village
    await ctx.send(f"Village '{name}' created and you have joined it!")

@bot.command()
async def join_village(ctx, name: str):
    if ctx.guild.id not in worlds:
        await ctx.send("A world must be created in this server before joining a village!")
        return

    if ctx.author.id not in characters:
        await ctx.send("You must create a character before joining a village!")
        return

    if ctx.guild.id not in villages or name not in villages[ctx.guild.id]:
        await ctx.send("This village does not exist in this server!")
        return

    village = villages[ctx.guild.id][name]

    if ctx.author.id in village['members']:
        await ctx.send("You are already a member of this village!")
        return

    village['members'].append(ctx.author.id)
    await ctx.send(f"You have joined the village '{name}'!")
        
@bot.command()
async def dump(ctx):
    if ctx.guild.id not in worlds:
        await ctx.send("A world must be created in this server before using the dump command!")
        return

    if ctx.author.id not in characters:
        await ctx.send("You must create a character before using the dump command!")
        return

    village_name = None
    for village in villages[ctx.guild.id].values():
        if ctx.author.id in village['members']:
            village_name = village['name']
            break

    if not village_name:
        await ctx.send("You must join a village before using the dump command!")
        return

    character = characters[ctx.author.id]
    village = villages[ctx.guild.id][village_name]

    if not character['inventory']:
        await ctx.send("Your inventory is empty.")
        return

    if "inventory" not in village:
        village["inventory"] = {}

    for item, quantity in character['inventory'].items():
        if item in village["inventory"]:
            village["inventory"][item] += quantity
        else:
            village["inventory"][item] = quantity

    character['inventory'] = {}
    await ctx.send(f"All items from your inventory have been dumped into the village '{village_name}' inventory!")
    
@bot.command()
async def village_inventory(ctx):
    if ctx.guild.id not in worlds:
        await ctx.send("A world must be created in this server before using the village_inventory command!")
        return

    if ctx.author.id not in characters:
        await ctx.send("You must create a character before using the village_inventory command!")
        return

    village_name = None
    for village in villages[ctx.guild.id].values():
        if ctx.author.id in village['members']:
            village_name = village['name']
            break

    if not village_name:
        await ctx.send("You must join a village before using the village_inventory command!")
        return

    village = villages[ctx.guild.id][village_name]

    if "inventory" not in village or not village["inventory"]:
        await ctx.send(f"The village '{village_name}' inventory is empty.")
    else:
        inventory_list = "\n".join([f"{key}: {value}" for key, value in village["inventory"].items()])
        await ctx.send(f"The village '{village_name}' inventory:\n```\n{inventory_list}\n```")

# Create the "reflect" command
@bot.command()
async def reflect(ctx):
    if ctx.author.id not in characters:
        await ctx.send("You must create a character before using the reflect command!")
        return

    character = characters[ctx.author.id]

    if character['actions'] < 1:
        await ctx.send("You don't have enough actions!")
        return

    village_name = None
    for village in villages[ctx.guild.id].values():
        if ctx.author.id in village['members']:
            village_name = village['name']
            break

    if not village_name:
        await ctx.send("You must join a village before using the reflect command!")
        return

    village = villages[ctx.guild.id][village_name]

    # Check if the village has discovered the "SHAPING" technology
    if "SHAPING" not in village["technologies"]:
        # Check if the character has enough PStoning points and the village has enough stones
        if character['PStoning'] >= 1 and village["inventory"].get("stones", 0) >= 300:
            # Calculate the chance of discovering the "SHAPING" technology
            chance = 0.01 * village['reflect_attempts']
            if random.random() < chance:
                village["technologies"].append("SHAPING")
                village['reflect_attempts'] = 0
                await ctx.send("You discovered the 'SHAPING' technology!")
            else:
                village['reflect_attempts'] += 1

    character['actions'] -= 1
    await ctx.send("You spent some time reflecting, but didn't discover any new technology.")

@bot.command()
async def cut_wood(ctx):
    if ctx.guild.id not in worlds:
        await ctx.send("A world must be created in this server before cutting wood!")
        return

    if ctx.author.id not in characters:
        await ctx.send("You must create a character before cutting wood!")
        return

    character = characters[ctx.author.id]

    if character['actions'] < 1:
        await ctx.send("You don't have enough actions!")
        return

    world = worlds[ctx.guild.id]
    if sum(world['trees']) == 0:
        await ctx.send("There are no trees left in the world!")
        return

    village_name = None
    for village in villages[ctx.guild.id].values():
        if ctx.author.id in village['members']:
            village_name = village['name']
            break

    if not village_name:
        await ctx.send("You must join a village before cutting wood!")
        return

    village = villages[ctx.guild.id][village_name]
    if village["inventory"].get("Stone Axe", 0) < 1:
        await ctx.send("Your village doesn't have a 'Stone Axe' in the inventory!")
        return

    # Cut a random tree in the world
    tree_index = random.randint(0, len(world['trees']) - 1)
    while world['trees'][tree_index] == 0:
        tree_index = random.randint(0, len(world['trees']) - 1)
    world['trees'][tree_index] -= 1

    # Update character stats
    wood_collected = character.get('woodinglevel', 1)
    character['inventory']['wood'] = character['inventory'].get('wood', 0) + wood_collected
    character['PWooding'] = character.get('PWooding', 0) + 0.01
    character['WoodingXP'] = character.get('WoodingXP', 0) + 1
    character['actions'] -= 1

    # Check if Wooding XP is enough to level up
    if character['WoodingXP'] >= 100 * (1.5 ** (character.get('woodinglevel', 1) - 1)):
        character['woodinglevel'] = character.get('woodinglevel', 1) + 1
        character['WoodingXP'] = 0
        await ctx.send(f"Your wooding just got better!")

    await ctx.send(f"You cut down a tree and collected {wood_collected} wood, gained {character.get('woodinglevel', 1) * 0.001} PWooding points, and 1 Wooding XP!")

# Create the "shaping" command
@bot.command()
async def shaping(ctx):
    if ctx.author.id not in characters:
        await ctx.send("You must create a character before using the shaping command!")
        return

    village_name = None
    for village in villages[ctx.guild.id].values():
        if ctx.author.id in village['members']:
            village_name = village['name']
            break

    if not village_name:
        await ctx.send("You must join a village before using the shaping command!")
        return

    village = villages[ctx.guild.id][village_name]

    # Check if the village has discovered the "SHAPING" technology
    if "SHAPING" not in village["technologies"]:
        await ctx.send("Your village hasn't discovered the 'SHAPING' technology yet!")
        return

    # Check if the village has enough stones
    if village["inventory"].get("stones", 0) < 2:
        await ctx.send("Your village doesn't have enough stones!")
        return

    # Update the village's inventory
    village["inventory"]["stones"] -= 2
    if "Stone Axe" in village["inventory"]:
        village["inventory"]["Stone Axe"] += 1
    else:
        village["inventory"]["Stone Axe"] = 1

    await ctx.send("You used 2 stones to create a 'Stone Axe' for your village!")

@bot.command()
async def save_data_cmd(ctx):
    if ctx.author.id == 362331212192153610:
        await ctx.send("Saving data...")

        # Save data and close the database connection
        global conn
        save_data(conn, "worlds", worlds)
        save_data(conn, "characters", characters)
        save_data(conn, "villages", villages)

        print("Data saved:")  # Add these lines
        print("Worlds:", worlds)
        print("Characters:", characters)
        print("Villages:", villages)

        await ctx.send("Data saved successfully!")
    else:
        await ctx.send("You don't have permission to save data.")

@bot.command()
async def close(ctx):
    if ctx.author.id == 362331212192153610:
        await ctx.send("Closing the bot...")
        await bot.close()
    else:
        await ctx.send("You don't have permission to close the bot.")

def calculate_death_chance(age, health):
    if age <= 9:
        return 50 / health
    elif 10 <= age <= 19:
        return 10 / health
    elif 20 <= age <= 29:
        return 150 / health
    elif 30 <= age <= 39:
        return 200 / health
    elif 40 <= age <= 49:
        return 510 / health
    elif 50 <= age <= 59:
        return 1000 / health
    elif 60 <= age <= 69:
        return 4000 / health
    elif 70 <= age <= 79:
        return 14000 / health
    elif 80 <= age <= 90:
        return 35000 / health
    elif 90 <= age <= 99:
        return 70000 / health
    else:
        return 90000 / health

@tasks.loop(hours=24)
async def age_increment_task():
    for character in characters.values():
        character['age'] += 1


@tasks.loop(hours=24)
async def actions_reset_task():
    for character in characters.values():
        character['actions'] = 16

@tasks.loop(hours=24)
async def death_check_task():
    to_delete = []
    for user_id, character in characters.items():
        death_chance = calculate_death_chance(character['age'], character['health'])
        if random.random() * 100 < death_chance:  # Multiply by 100 to match the percentage range
            to_delete.append(user_id)
            # Notify the user about the character's death
            user = bot.get_user(user_id)
            if user:
                await user.send(f"Your character '{character['name']}' has died at the age of {character['age']}.")

    for user_id in to_delete:
        del characters[user_id]
        


age_increment_task.before_loop
async def before_age_increment_task():
    await bot.wait_until_ready()

actions_reset_task.before_loop
async def before_actions_reset_task():
    await bot.wait_until_ready()

death_check_task.before_loop
async def before_death_check_task():
    await bot.wait_until_ready()
    


bot.run(os.environ['BOT_TOKEN'])
