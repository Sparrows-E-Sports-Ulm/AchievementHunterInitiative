import discord
import os
from dotenv import load_dotenv
from discord import app_commands
from user import Hunter
from scoreboard_calculator import calculate_scoreboard
from scoreboard_calculator import calculate_scoreboard_around_hunter
import threading
import pickle
from table2ascii import table2ascii as t2a, PresetStyle

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
TOKEN = str(os.getenv("BOT_TOKEN"))
SERVERID = int(os.getenv("SERVER_ID"))



registered_hunters = dict() # SteamID : Hunter
being_registeres = []
error_counter = 0



directory = os.fsencode("Hunters")
    
for file in os.listdir(directory):
    filename = os.fsdecode(file)
    print(filename)
    if(filename.endswith(".hunt")):
        try:
            with open("Hunters/" + filename, "rb") as f:
                hunter : Hunter = pickle.load(f)
                registered_hunters[hunter.name] = hunter
        except Exception as e:
            print("Couldn't load Hunter")


@tree.command(
    name="register",
    description="Registers a new Achievement Hunter. It may take a few minutes.",
    guild = discord.Object(id=SERVERID)
)
async def register(interaction, steam_id : str):
    message : str
    print(being_registeres)
    try:
        if(steam_id in registered_hunters.keys()):
            message="SteamID already Registered. Use /score to see the recorded score."
        elif(steam_id in being_registeres):
            message="Hunter is currently being registered. Please be patient."
        else:
            thread = threading.Thread(target=register_user, args=(steam_id,))
            thread.start()
            message="Achievement Hunter is being registered. This may take a while."
    except Exception as e:
        message="Registration failed. Please Verify the SteamID is written correctly. Alternatively, send us a ticket using /error."
        e.with_traceback()

    await interaction.response.send_message(message)

def register_user(steam_id, ):
    being_registeres.append(steam_id)
    print("Registering User")
    hunter = Hunter(steam_id)
    file = open("Hunters/" + hunter.name + ".hunt", "wb")
    pickle.dump(hunter, file)
    registered_hunters[steam_id] = hunter
    being_registeres.remove(steam_id)

@tree.command(
        name="update",
        description="Update Single Hunter",
        guild=discord.Object(id=SERVERID)
)
async def update(interaction, steam_id : str):
    try:
        if(steam_id not in registered_hunters.keys()):
            message = "User not Registered. Use /register to register a new Achievement Hunter"
        elif(steam_id in being_registeres):
            message="Hunter is currently being updated. Please be patient."
        else:
            thread = threading.Thread(target=register_user, args=(steam_id,))
            thread.start()
            message="Achievement Hunter is being updated. This may take a while."
    except Exception as e:
        message="Registration failed. Please Verify the SteamID is written correctly. Alternatively, send us a ticket using /error."
        e.with_traceback()

    await interaction.response.send_message(message)
@tree.command(
    name="scoreboard",
    description="Shows the Scoreboard",
    guild = discord.Object(id=SERVERID)
)
async def scoreboard(interaction):
    output = t2a(
        header=["Rank","Hunter", "Team"],
        body=calculate_scoreboard(registered_hunters),
        style=PresetStyle.thin_compact
)
    await interaction.response.send_message(f"```\n{output}\n```")

@tree.command(
    name="scoreboard_hunter",
    description="Shows the Scoreboard around an individual",
    guild = discord.Object(id=SERVERID)
)
async def scoreboard_hunter(interaction, steam_id : str):
    output = t2a(
        header=["Rank","Hunter", "Score"],
        body=calculate_scoreboard_around_hunter(registered_hunters, steam_id),
        style=PresetStyle.thin_compact
)
    await interaction.response.send_message(f"```\n{output}\n```")
@tree.command(
    name = "score",
    description="Shows the score of a given SteamID",
    guild = discord.Object(id=SERVERID)
)
async def score(interaction, steam_id : str):
    message : str
    print(registered_hunters.keys())
    if(not steam_id in registered_hunters.keys()):
        message = "User not Registered. Use /register to register a new Achievement Hunter"
    else:
        try:
            hunter : Hunter = registered_hunters[steam_id]
            message = str(hunter.score)
        except Exception as e:
            message="Request failed. Please Verify the SteamID is written correctly. Alternatively, send us a ticket using /error."
            e.with_traceback()
    await interaction.response.send_message(message)

@tree.command(
    name = "error",
    description = "Send us information about a error you encountered",
    guild = discord.Object(id=SERVERID)
)
async def error(interaction, error_message : str, error_counter : int = error_counter):
    with open("Errors/error-" + str(error_counter), "w") as file:
        file.write(error_message)
    error_counter += 1
    await interaction.response.send_message("Error has been reported")

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=SERVERID))
    print('We have logged in as {0.user}'.format(client))

#@client.event
#async def on_message(message):
#    if message.author == client.user:
#        return

#    if message.content.startswith('$hello'):
#        await message.channel.send('Hello!')

client.run(TOKEN)

