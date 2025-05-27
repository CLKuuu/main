import discord
from discord.ext import commands
import os
import json
import asyncio
from datetime import datetime, timedelta

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Supprimer la commande help par défaut
bot.remove_command('help')

# Stockage des données (normalement dans une base de données)
user_levels = {}
user_warnings = {}
guild_settings = {}

# Système anti-raid
guild_antiraid = {}
recent_joins = {}
user_message_count = {}

# Configuration anti-raid par défaut
DEFAULT_ANTIRAID_CONFIG = {
    "enabled": True,
    "max_joins_per_minute": 5,
    "max_messages_per_minute": 10,
    "auto_ban_duration": 300,  # 5 minutes en secondes
    "alert_channel": None
}

# Système de niveaux
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Système de niveaux
    user_id = str(message.author.id)
    guild_id = str(message.guild.id)

    if guild_id not in user_levels:
        user_levels[guild_id] = {}

    if user_id not in user_levels[guild_id]:
        user_levels[guild_id][user_id] = {"xp": 0, "level": 1}

    # Ajouter de l'XP (1-5 XP par message)
    import random
    xp_gain = random.randint(1, 5)
    user_levels[guild_id][user_id]["xp"] += xp_gain

    # Calculer le niveau
    xp = user_levels[guild_id][user_id]["xp"]
    level = int(xp / 100) + 1
    old_level = user_levels[guild_id][user_id]["level"]

    if level > old_level:
        user_levels[guild_id][user_id]["level"] = level
        await message.channel.send(f"🎉 {message.author.mention} a atteint le niveau {level}!")

    # Auto-modération (mots interdits)
    banned_words = ["spam", "idiot", "nul"]
    if any(word in message.content.lower() for word in banned_words):
        await message.delete()
        await message.channel.send(f"⚠️ {message.author.mention}, ce message a été supprimé (langage inapproprié)!")

    # Système anti-raid pour les messages
    await check_message_spam(message)

    await bot.process_commands(message)

# Messages de bienvenue et au revoir
@bot.event
async def on_member_join(member):
    guild_id = str(member.guild.id)
    
    # Système anti-raid
    await check_raid_joins(member)
    
    # Rôle automatique
    if guild_id in guild_settings and "autorole" in guild_settings[guild_id]:
        role_id = guild_settings[guild_id]["autorole"]
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role, reason="Rôle automatique")
            except discord.Forbidden:
                pass
    
    if guild_id in guild_settings and "welcome_channel" in guild_settings[guild_id]:
        channel_id = guild_settings[guild_id]["welcome_channel"]
        channel = bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="👋 Bienvenue!",
                description=f"Bienvenue {member.mention} sur **{member.guild.name}**!\n\nNous sommes maintenant {member.guild.member_count} membres!",
                color=0x00ff00
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    guild_id = str(member.guild.id)
    if guild_id in guild_settings and "goodbye_channel" in guild_settings[guild_id]:
        channel_id = guild_settings[guild_id]["goodbye_channel"]
        channel = bot.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="👋 Au revoir!",
                description=f"**{member.name}** a quitté le serveur...\n\nNous sommes maintenant {member.guild.member_count} membres.",
                color=0xff0000
            )
            await channel.send(embed=embed)

# Commande Help
@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title="📋 Liste des Commandes",
        description="Voici toutes les commandes disponibles:",
        color=0x0099ff
    )

    embed.add_field(
        name="🔨 Modération",
        value="`!kick @user [raison]` - Kick un utilisateur\n`!ban @user [raison]` - Ban un utilisateur\n`!warn @user [raison]` - Warn un utilisateur\n`!warnings @user` - Voir les warns d'un user",
        inline=False
    )

    embed.add_field(
        name="🎫 Tickets",
        value="`!ticket` - Créer un ticket\n`!close` - Fermer un ticket",
        inline=False
    )

    embed.add_field(
        name="📨 Messages",
        value="`!send #salon message` - Envoyer un message\n`!poll question` - Créer un sondage\n`!suggest suggestion` - Faire une suggestion",
        inline=False
    )

    embed.add_field(
        name="📊 Niveaux",
        value="`!level [@user]` - Voir le niveau\n`!leaderboard` - Classement du serveur",
        inline=False
    )

    embed.add_field(
        name="⚙️ Configuration",
        value="`!setwelcome #salon` - Définir le salon de bienvenue\n`!setgoodbye #salon` - Définir le salon d'au revoir\n`!antiraid` - Configurer l'anti-raid",
        inline=False
    )

    embed.add_field(
        name="🛡️ Anti-Raid",
        value="`!antiraid status` - Statut de l'anti-raid\n`!antiraid toggle` - Activer/Désactiver\n`!antiraid config` - Configuration\n`!antiraid alert #salon` - Salon d'alerte",
        inline=False
    )

    embed.add_field(
        name="🎮 Commandes Fun",
        value="`!amour [@user]` - Calculer le pourcentage d'amour\n`!lgbt [@user]` - Détecteur LGBT+\n`!hetero [@user]` - Détecteur hétéro\n`!ship [@user1] [@user2]` - Ship deux personnes",
        inline=False
    )

    embed.add_field(
        name="🎮 Commandes Fun",
        value="`!joke` - Raconte une blague\n`!8ball question` - Boule magique\n`!dice [faces]` - Lance un dé\n`!flip` - Lance une pièce\n`!choose opt1, opt2, opt3` - Choix aléatoire\n`!quote` - Citation inspirante\n`!avatar [@user]` - Affiche l'avatar",
        inline=False
    )

    embed.add_field(
        name="💰 Économie",
        value="`!balance [@user]` - Voir le solde\n`!daily` - Récompense quotidienne\n`!work` - Travailler pour gagner\n`!gamble <montant>` - Parier au casino\n`!give @user <montant>` - Donner des coins",
        inline=False
    )

    embed.add_field(
        name="🎯 Mini-Jeux",
        value="`!rps <choix>` - Pierre-papier-ciseaux\n`!memory` - Jeu de mémoire\n`!guess <nombre>` - Deviner le nombre",
        inline=False
    )

    embed.add_field(
        name="🛠️ Utilitaires",
        value="`!calc <expression>` - Calculatrice\n`!translate <lang> <texte>` - Traduction\n`!weather [ville]` - Météo\n`!qr <texte>` - Code QR",
        inline=False
    )

    embed.add_field(
        name="🎂 Social",
        value="`!birthday JJ/MM` - Définir anniversaire\n`!birthdays` - Liste anniversaires\n`!rep @user [raison]` - Donner réputation\n`!reputation [@user]` - Voir réputation",
        inline=False
    )

    embed.add_field(
        name="🎵 Musique",
        value="`!music` - Guide musical",
        inline=False
    )

    embed.add_field(
        name="📨 Messages & Annonces",
        value="`!dmall <message>` - Envoyer DM à tous (Admin)\n`!dmuser @user <message>` - DM à un utilisateur\n`!announce #salon <message>` - Annonce officielle",
        inline=False
    )

    await ctx.send(embed=embed)

# Fonctions système anti-raid
async def check_raid_joins(member):
    guild_id = str(member.guild.id)
    current_time = datetime.now()
    
    # Initialiser les données si nécessaire
    if guild_id not in guild_antiraid:
        guild_antiraid[guild_id] = DEFAULT_ANTIRAID_CONFIG.copy()
    
    if guild_id not in recent_joins:
        recent_joins[guild_id] = []
    
    config = guild_antiraid[guild_id]
    if not config["enabled"]:
        return
    
    # Ajouter le join récent
    recent_joins[guild_id].append(current_time)
    
    # Nettoyer les joins de plus d'une minute
    cutoff_time = current_time - timedelta(minutes=1)
    recent_joins[guild_id] = [join_time for join_time in recent_joins[guild_id] if join_time > cutoff_time]
    
    # Vérifier si le seuil est dépassé
    if len(recent_joins[guild_id]) > config["max_joins_per_minute"]:
        await handle_raid_detected(member.guild, "join_spam")

async def check_message_spam(message):
    if message.author.bot:
        return
    
    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    current_time = datetime.now()
    
    if guild_id not in guild_antiraid:
        guild_antiraid[guild_id] = DEFAULT_ANTIRAID_CONFIG.copy()
    
    config = guild_antiraid[guild_id]
    if not config["enabled"]:
        return
    
    # Initialiser le compteur de messages
    if guild_id not in user_message_count:
        user_message_count[guild_id] = {}
    
    if user_id not in user_message_count[guild_id]:
        user_message_count[guild_id][user_id] = []
    
    # Ajouter le message
    user_message_count[guild_id][user_id].append(current_time)
    
    # Nettoyer les messages de plus d'une minute
    cutoff_time = current_time - timedelta(minutes=1)
    user_message_count[guild_id][user_id] = [
        msg_time for msg_time in user_message_count[guild_id][user_id] 
        if msg_time > cutoff_time
    ]
    
    # Vérifier le spam
    if len(user_message_count[guild_id][user_id]) > config["max_messages_per_minute"]:
        await handle_spam_detected(message.author, "message_spam")

async def handle_raid_detected(guild, raid_type):
    guild_id = str(guild.id)
    config = guild_antiraid[guild_id]
    
    # Envoyer une alerte
    if config["alert_channel"]:
        channel = guild.get_channel(config["alert_channel"])
        if channel:
            embed = discord.Embed(
                title="🚨 RAID DÉTECTÉ!",
                description=f"**Type:** {raid_type}\n**Serveur:** {guild.name}\n**Heure:** {datetime.now().strftime('%H:%M:%S')}",
                color=0xff0000
            )
            embed.add_field(
                name="⚡ Action Automatique",
                value="Les nouveaux membres seront surveillés de près.",
                inline=False
            )
            await channel.send(embed=embed)

async def handle_spam_detected(member, spam_type):
    guild_id = str(member.guild.id)
    config = guild_antiraid[guild_id]
    
    try:
        # Timeout temporaire (5 minutes)
        timeout_until = datetime.now() + timedelta(seconds=config["auto_ban_duration"])
        await member.timeout(timeout_until, reason="Anti-raid: Spam détecté")
        
        # Alerter les modérateurs
        if config["alert_channel"]:
            channel = member.guild.get_channel(config["alert_channel"])
            if channel:
                embed = discord.Embed(
                    title="🔇 Membre mis en timeout",
                    description=f"**Membre:** {member.mention}\n**Raison:** Spam détecté\n**Durée:** {config['auto_ban_duration']} secondes",
                    color=0xffa500
                )
                await channel.send(embed=embed)
                
    except discord.Forbidden:
        pass  # Pas de permissions pour timeout

# Commandes anti-raid
@bot.command(name='antiraid')
async def antiraid_command(ctx, action=None, *, value=None):
    if not ctx.author.guild_permissions.manage_guild:
        await ctx.send("❌ Vous n'avez pas la permission de configurer l'anti-raid!")
        return
    
    guild_id = str(ctx.guild.id)
    
    # Initialiser si nécessaire
    if guild_id not in guild_antiraid:
        guild_antiraid[guild_id] = DEFAULT_ANTIRAID_CONFIG.copy()
    
    config = guild_antiraid[guild_id]
    
    if not action:
        # Afficher le menu principal
        embed = discord.Embed(
            title="🛡️ Système Anti-Raid",
            description="Configuration du système de protection",
            color=0x00aaff
        )
        
        status = "🟢 Activé" if config["enabled"] else "🔴 Désactivé"
        embed.add_field(name="Statut", value=status, inline=True)
        
        alert_channel = "Aucun" if not config["alert_channel"] else f"<#{config['alert_channel']}>"
        embed.add_field(name="Salon d'alerte", value=alert_channel, inline=True)
        
        embed.add_field(name="Max joins/minute", value=str(config["max_joins_per_minute"]), inline=True)
        embed.add_field(name="Max messages/minute", value=str(config["max_messages_per_minute"]), inline=True)
        embed.add_field(name="Durée timeout (sec)", value=str(config["auto_ban_duration"]), inline=True)
        
        embed.add_field(
            name="📋 Commandes",
            value="`!antiraid toggle` - Activer/Désactiver\n`!antiraid alert #salon` - Définir salon d'alerte\n`!antiraid config` - Configuration avancée",
            inline=False
        )
        
        await ctx.send(embed=embed)
        return
    
    if action.lower() == "toggle":
        config["enabled"] = not config["enabled"]
        status = "activé" if config["enabled"] else "désactivé"
        embed = discord.Embed(
            title="🛡️ Anti-Raid",
            description=f"Système anti-raid **{status}**",
            color=0x00ff00 if config["enabled"] else 0xff0000
        )
        await ctx.send(embed=embed)
        
    elif action.lower() == "alert":
        if not value:
            await ctx.send("❌ Mentionnez un salon ! Exemple: `!antiraid alert #logs`")
            return
        
        try:
            channel = await commands.TextChannelConverter().convert(ctx, value)
            config["alert_channel"] = channel.id
            await ctx.send(f"✅ Salon d'alerte défini sur {channel.mention}")
        except:
            await ctx.send("❌ Salon introuvable!")
            
    elif action.lower() == "config":
        embed = discord.Embed(
            title="⚙️ Configuration Anti-Raid",
            description="Configuration actuelle du système",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🔧 Paramètres modifiables",
            value=f"**Max joins/minute:** {config['max_joins_per_minute']}\n**Max messages/minute:** {config['max_messages_per_minute']}\n**Durée timeout:** {config['auto_ban_duration']}s",
            inline=False
        )
        
        embed.add_field(
            name="📝 Pour modifier",
            value="Contactez un administrateur pour ajuster ces valeurs selon vos besoins.",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    elif action.lower() == "status":
        embed = discord.Embed(
            title="📊 Statut Anti-Raid",
            color=0x00aaff
        )
        
        status = "🟢 Activé" if config["enabled"] else "🔴 Désactivé"
        embed.add_field(name="Statut", value=status, inline=False)
        
        # Statistiques récentes
        current_joins = len(recent_joins.get(guild_id, []))
        embed.add_field(name="Joins récents (1min)", value=str(current_joins), inline=True)
        
        total_monitored = len(user_message_count.get(guild_id, {}))
        embed.add_field(name="Utilisateurs surveillés", value=str(total_monitored), inline=True)
        
        await ctx.send(embed=embed)
        
    else:
        await ctx.send("❌ Action inconnue! Utilisez: `toggle`, `alert`, `config`, ou `status`")

# Système de warns
@bot.command(name='warn')
async def warn_user(ctx, member: discord.Member, *, reason=None):
    if not ctx.author.guild_permissions.kick_members:
        await ctx.send("❌ Vous n'avez pas la permission de warn des membres!")
        return

    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    if guild_id not in user_warnings:
        user_warnings[guild_id] = {}

    if user_id not in user_warnings[guild_id]:
        user_warnings[guild_id][user_id] = []

    warning = {
        "reason": reason or "Aucune raison spécifiée",
        "moderator": str(ctx.author.id),
        "date": datetime.now().isoformat()
    }

    user_warnings[guild_id][user_id].append(warning)
    warn_count = len(user_warnings[guild_id][user_id])

    embed = discord.Embed(
        title="⚠️ Avertissement",
        description=f"{member.mention} a reçu un avertissement",
        color=0xffaa00
    )
    embed.add_field(name="Raison", value=reason or "Aucune raison spécifiée", inline=False)
    embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
    embed.add_field(name="Total des warns", value=str(warn_count), inline=True)

    await ctx.send(embed=embed)

@bot.command(name='warnings')
async def show_warnings(ctx, member: discord.Member):
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    if guild_id not in user_warnings or user_id not in user_warnings[guild_id]:
        await ctx.send(f"{member.mention} n'a aucun avertissement.")
        return

    warnings = user_warnings[guild_id][user_id]

    embed = discord.Embed(
        title=f"⚠️ Avertissements de {member.display_name}",
        description=f"Total: {len(warnings)} avertissement(s)",
        color=0xff0000
    )

    for i, warning in enumerate(warnings[-5:], 1):  # Afficher les 5 derniers
        moderator = ctx.guild.get_member(int(warning["moderator"]))
        mod_name = moderator.display_name if moderator else "Modérateur inconnu"
        date = datetime.fromisoformat(warning["date"]).strftime("%d/%m/%Y")

        embed.add_field(
            name=f"Warn #{i}",
            value=f"**Raison:** {warning['reason']}\n**Modérateur:** {mod_name}\n**Date:** {date}",
            inline=False
        )

    await ctx.send(embed=embed)

# Configuration des salons
@bot.command(name='setwelcome')
async def set_welcome_channel(ctx, channel: discord.TextChannel):
    if not ctx.author.guild_permissions.manage_guild:
        await ctx.send("❌ Vous n'avez pas la permission de configurer le serveur!")
        return

    guild_id = str(ctx.guild.id)
    if guild_id not in guild_settings:
        guild_settings[guild_id] = {}

    guild_settings[guild_id]["welcome_channel"] = channel.id
    await ctx.send(f"✅ Salon de bienvenue défini sur {channel.mention}")

@bot.command(name='setgoodbye')
async def set_goodbye_channel(ctx, channel: discord.TextChannel):
    if not ctx.author.guild_permissions.manage_guild:
        await ctx.send("❌ Vous n'avez pas la permission de configurer le serveur!")
        return

    guild_id = str(ctx.guild.id)
    if guild_id not in guild_settings:
        guild_settings[guild_id] = {}

    guild_settings[guild_id]["goodbye_channel"] = channel.id
    await ctx.send(f"✅ Salon d'au revoir défini sur {channel.mention}")

# Système de niveaux
@bot.command(name='level')
async def show_level(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    if guild_id not in user_levels or user_id not in user_levels[guild_id]:
        await ctx.send(f"{member.mention} n'a pas encore de niveau.")
        return

    data = user_levels[guild_id][user_id]
    level = data["level"]
    xp = data["xp"]
    xp_needed = level * 100

    embed = discord.Embed(
        title=f"📊 Niveau de {member.display_name}",
        color=0x00ff00
    )
    embed.add_field(name="Niveau", value=str(level), inline=True)
    embed.add_field(name="XP", value=f"{xp}/{xp_needed}", inline=True)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

    await ctx.send(embed=embed)

@bot.command(name='leaderboard')
async def leaderboard(ctx):
    guild_id = str(ctx.guild.id)

    if guild_id not in user_levels:
        await ctx.send("Aucune donnée de niveau disponible.")
        return

    # Trier les utilisateurs par niveau puis par XP
    sorted_users = sorted(
        user_levels[guild_id].items(),
        key=lambda x: (x[1]["level"], x[1]["xp"]),
        reverse=True
    )

    embed = discord.Embed(
        title="🏆 Classement du Serveur",
        color=0xffd700
    )

    for i, (user_id, data) in enumerate(sorted_users[:10], 1):
        user = ctx.guild.get_member(int(user_id))
        if user:
            embed.add_field(
                name=f"#{i} {user.display_name}",
                value=f"Niveau {data['level']} - {data['xp']} XP",
                inline=False
            )

    await ctx.send(embed=embed)

# Sondages
@bot.command(name='poll')
async def create_poll(ctx, *, question):
    embed = discord.Embed(
        title="📊 Sondage",
        description=question,
        color=0x0099ff
    )
    embed.set_footer(text=f"Sondage créé par {ctx.author.display_name}")

    message = await ctx.send(embed=embed)
    await message.add_reaction("✅")
    await message.add_reaction("❌")

# Suggestions
@bot.command(name='suggest')
async def suggest(ctx, *, suggestion):
    embed = discord.Embed(
        title="💡 Nouvelle Suggestion",
        description=suggestion,
        color=0xffaa00
    )
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    embed.set_footer(text=f"Suggestion #{ctx.message.id}")

    message = await ctx.send(embed=embed)
    await message.add_reaction("👍")
    await message.add_reaction("👎")
    await message.add_reaction("🤷")

# Commandes amusantes avec pourcentages
@bot.command(name='amour', aliases=['love'])
async def love_percentage(ctx, user: discord.Member = None):
    import random
    
    if user is None:
        # Sélectionner un utilisateur aléatoire du serveur
        members = [m for m in ctx.guild.members if not m.bot and m != ctx.author]
        if not members:
            await ctx.send("❌ Aucun autre membre trouvé sur le serveur!")
            return
        user = random.choice(members)
    
    if user == ctx.author:
        await ctx.send("💝 L'amour de soi est important ! 100% d'amour pour vous-même! 💖")
        return
    
    # Générer un pourcentage basé sur les IDs pour être cohérent
    seed = abs(hash(f"{ctx.author.id}{user.id}")) % 101
    random.seed(seed)
    percentage = random.randint(0, 100)
    
    # Messages selon le pourcentage
    if percentage >= 90:
        emoji = "💖💕💖"
        message = "C'est l'amour parfait !"
    elif percentage >= 70:
        emoji = "💕💖"
        message = "Belle histoire d'amour en perspective !"
    elif percentage >= 50:
        emoji = "💗"
        message = "Il y a du potentiel !"
    elif percentage >= 30:
        emoji = "💓"
        message = "Amitié possible..."
    else:
        emoji = "💔"
        message = "Peut-être pas fait l'un pour l'autre..."
    
    embed = discord.Embed(
        title=f"{emoji} Compteur d'Amour {emoji}",
        description=f"**{ctx.author.display_name}** 💖 **{user.display_name}**",
        color=0xff69b4
    )
    embed.add_field(
        name="💕 Pourcentage d'amour",
        value=f"**{percentage}%**",
        inline=True
    )
    embed.add_field(
        name="💭 Verdict",
        value=message,
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='lgbt')
async def lgbt_percentage(ctx, user: discord.Member = None):
    import random
    
    target = user if user else ctx.author
    
    # Générer un pourcentage basé sur l'ID pour être cohérent
    seed = abs(hash(f"lgbt{target.id}")) % 101
    random.seed(seed)
    percentage = random.randint(0, 100)
    
    # Messages et drapeaux selon le pourcentage
    flags = ["🏳️‍🌈", "🏳️‍⚧️", "💜", "💖", "💙", "💛", "🤍"]
    flag = random.choice(flags)
    
    if percentage >= 80:
        message = "Très probablement ! Soyez fier de qui vous êtes ! 🌈"
    elif percentage >= 60:
        message = "Il y a de bonnes chances ! L'amour n'a pas de limites ! 💖"
    elif percentage >= 40:
        message = "Peut-être... explorez votre vraie identité ! 🏳️‍🌈"
    elif percentage >= 20:
        message = "Probablement pas, mais on ne sait jamais ! 💕"
    else:
        message = "Peu probable, mais restez ouvert d'esprit ! 🌈"
    
    embed = discord.Embed(
        title=f"{flag} Détecteur LGBT+ {flag}",
        description=f"Analyse de **{target.display_name}**",
        color=0x9932cc
    )
    embed.add_field(
        name="🏳️‍🌈 Pourcentage LGBT+",
        value=f"**{percentage}%**",
        inline=True
    )
    embed.add_field(
        name="💭 Analyse",
        value=message,
        inline=False
    )
    embed.set_footer(text="Note: Ceci est purement amusant et ne reflète aucune réalité !")
    
    await ctx.send(embed=embed)

@bot.command(name='hetero', aliases=['straight'])
async def hetero_percentage(ctx, user: discord.Member = None):
    import random
    
    target = user if user else ctx.author
    
    # Générer un pourcentage basé sur l'ID pour être cohérent
    seed = abs(hash(f"hetero{target.id}")) % 101
    random.seed(seed)
    percentage = random.randint(0, 100)
    
    if percentage >= 80:
        message = "Très probablement hétéro ! 💑"
    elif percentage >= 60:
        message = "Plutôt hétéro ! 👫"
    elif percentage >= 40:
        message = "Peut-être... ou peut-être pas ! 🤔"
    elif percentage >= 20:
        message = "Probablement pas complètement hétéro ! 🌈"
    else:
        message = "Définitivement pas hétéro ! 🏳️‍🌈"
    
    embed = discord.Embed(
        title="👫 Détecteur Hétéro 👬",
        description=f"Analyse de **{target.display_name}**",
        color=0x87ceeb
    )
    embed.add_field(
        name="💙 Pourcentage Hétéro",
        value=f"**{percentage}%**",
        inline=True
    )
    embed.add_field(
        name="💭 Analyse",
        value=message,
        inline=False
    )
    embed.set_footer(text="Note: Ceci est purement amusant et ne reflète aucune réalité !")
    
    await ctx.send(embed=embed)

@bot.command(name='ship')
async def ship_users(ctx, user1: discord.Member = None, user2: discord.Member = None):
    import random
    
    if user1 is None:
        user1 = ctx.author
    
    if user2 is None:
        # Sélectionner un utilisateur aléatoire
        members = [m for m in ctx.guild.members if not m.bot and m != user1]
        if not members:
            await ctx.send("❌ Aucun autre membre trouvé!")
            return
        user2 = random.choice(members)
    
    # Créer un nom de ship
    name1 = user1.display_name[:len(user1.display_name)//2]
    name2 = user2.display_name[len(user2.display_name)//2:]
    ship_name = name1 + name2
    
    # Générer un pourcentage de compatibilité
    seed = abs(hash(f"{user1.id}{user2.id}")) % 101
    random.seed(seed)
    percentage = random.randint(0, 100)
    
    if percentage >= 90:
        emoji = "💖💕💖"
        message = "Match parfait ! Mariage immédiat ! 💒"
    elif percentage >= 75:
        emoji = "💕💖"
        message = "Excellent couple ! 💑"
    elif percentage >= 60:
        emoji = "💗💓"
        message = "Belle relation possible ! 💏"
    elif percentage >= 40:
        emoji = "💓"
        message = "Amis avec bénéfices ? 😏"
    elif percentage >= 20:
        emoji = "💔"
        message = "Juste des amis... 👫"
    else:
        emoji = "💔💔"
        message = "Mieux vaut éviter... 🙈"
    
    embed = discord.Embed(
        title=f"{emoji} Ship Detector {emoji}",
        description=f"**{user1.display_name}** 💖 **{user2.display_name}**",
        color=0xff1493
    )
    embed.add_field(
        name="💕 Nom du couple",
        value=f"**{ship_name}**",
        inline=True
    )
    embed.add_field(
        name="💯 Compatibilité",
        value=f"**{percentage}%**",
        inline=True
    )
    embed.add_field(
        name="💭 Verdict",
        value=message,
        inline=False
    )
    
    await ctx.send(embed=embed)

# Commandes de modération existantes
@bot.command(name='kick')
async def kick_user(ctx, member: discord.Member, *, reason=None):
    if not ctx.author.guild_permissions.kick_members:
        await ctx.send("❌ Vous n'avez pas la permission de kick des membres!")
        return

    try:
        if reason:
            await member.kick(reason=f"Kicked by {ctx.author}: {reason}")
            await ctx.send(f"✅ {member.mention} a été kick pour: {reason}")
        else:
            await member.kick(reason=f"Kicked by {ctx.author}")
            await ctx.send(f"✅ {member.mention} a été kick")
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de kick ce membre!")
    except discord.HTTPException:
        await ctx.send("❌ Erreur lors du kick!")

@bot.command(name='ban')
async def ban_user(ctx, member: discord.Member, *, reason=None):
    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ Vous n'avez pas la permission de ban des membres!")
        return

    if member == ctx.author:
        await ctx.send("❌ Vous ne pouvez pas vous ban vous-même!")
        return

    if member == ctx.guild.me:
        await ctx.send("❌ Je ne peux pas me ban moi-même!")
        return

    try:
        if reason:
            await member.ban(reason=f"Banned by {ctx.author}: {reason}")
            await ctx.send(f"🔨 {member.mention} a été banni pour: {reason}")
        else:
            await member.ban(reason=f"Banned by {ctx.author}")
            await ctx.send(f"🔨 {member.mention} a été banni")
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de ban ce membre!")
    except discord.HTTPException:
        await ctx.send("❌ Erreur lors du ban!")

@bot.command(name='send')
async def send_message(ctx, channel: discord.TextChannel, *, message):
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("❌ Vous n'avez pas la permission d'envoyer des messages via le bot!")
        return

    try:
        await channel.send(message)
        await ctx.send(f"✅ Message envoyé dans {channel.mention}")
    except discord.Forbidden:
        await ctx.send(f"❌ Je n'ai pas la permission d'envoyer des messages dans {channel.mention}!")
    except discord.HTTPException:
        await ctx.send("❌ Erreur lors de l'envoi du message!")

# Commandes fun
@bot.command(name='joke')
async def tell_joke(ctx):
    """Raconte une blague aléatoire"""
    jokes = [
        "Pourquoi les plongeurs plongent-ils toujours en arrière et jamais en avant ? Parce que sinon, ils tombent dans le bateau !",
        "Que dit un escargot quand il croise une limace ? 'Regarde, un nudiste !'",
        "Comment appelle-t-on un chat tombé dans un pot de peinture le jour de Noël ? Un chat-mallow !",
        "Qu'est-ce qui est jaune et qui attend ? Jonathan !",
        "Pourquoi les poissons n'aiment pas jouer au tennis ? Parce qu'ils ont peur du filet !",
        "Comment appelle-t-on un boomerang qui ne revient pas ? Un bâton !",
        "Que dit un informaticien quand il s'ennuie ? 'Je me cache dans le terminal !'",
        "Pourquoi les développeurs préfèrent-ils les thés plutôt que les cafés ? Parce que Java, ça suffit !"
    ]
    
    import random
    joke = random.choice(jokes)
    
    embed = discord.Embed(
        title="😂 Blague du jour",
        description=joke,
        color=0xffff00
    )
    embed.set_footer(text="Tapez !joke pour une autre blague !")
    
    await ctx.send(embed=embed)

@bot.command(name='8ball')
async def magic_8ball(ctx, *, question=None):
    """Boule magique 8 - Pose une question !"""
    if not question:
        await ctx.send("❓ Pose-moi une question ! Exemple: `!8ball Est-ce que je vais réussir ?`")
        return
    
    responses = [
        "🔮 Oui, absolument !",
        "🔮 C'est certain !",
        "🔮 Sans aucun doute !",
        "🔮 Oui, définitivement !",
        "🔮 Tu peux compter dessus !",
        "🔮 Très probable !",
        "🔮 Les signes pointent vers oui !",
        "🔮 Réponse floue, réessaie !",
        "🔮 Demande plus tard !",
        "🔮 Mieux vaut ne pas te le dire maintenant !",
        "🔮 Ne compte pas dessus !",
        "🔮 Ma réponse est non !",
        "🔮 Mes sources disent non !",
        "🔮 Très douteux !",
        "🔮 Non, définitivement pas !"
    ]
    
    import random
    response = random.choice(responses)
    
    embed = discord.Embed(
        title="🎱 Boule Magique",
        color=0x800080
    )
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Réponse", value=response, inline=False)
    embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@bot.command(name='dice')
async def roll_dice(ctx, sides: int = 6):
    """Lance un dé (par défaut 6 faces)"""
    if sides < 2 or sides > 100:
        await ctx.send("❌ Le dé doit avoir entre 2 et 100 faces !")
        return
    
    import random
    result = random.randint(1, sides)
    
    embed = discord.Embed(
        title="🎲 Lancer de dé",
        description=f"**Résultat : {result}**",
        color=0x00ff00
    )
    embed.add_field(name="Dé", value=f"{sides} faces", inline=True)
    embed.add_field(name="Lancé par", value=ctx.author.mention, inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='flip')
async def flip_coin(ctx):
    """Lance une pièce"""
    import random
    result = random.choice(["Pile", "Face"])
    emoji = "🪙" if result == "Pile" else "🔄"
    
    embed = discord.Embed(
        title="🪙 Lancer de pièce",
        description=f"{emoji} **{result}**",
        color=0xffd700
    )
    embed.set_footer(text=f"Lancé par {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@bot.command(name='choose')
async def choose_option(ctx, *, options):
    """Choisit aléatoirement entre plusieurs options (sépare avec des virgules)"""
    if "," not in options:
        await ctx.send("❌ Sépare tes options avec des virgules ! Exemple: `!choose pizza, burger, sushi`")
        return
    
    choices = [choice.strip() for choice in options.split(",")]
    if len(choices) < 2:
        await ctx.send("❌ Il faut au moins 2 options !")
        return
    
    import random
    chosen = random.choice(choices)
    
    embed = discord.Embed(
        title="🤔 Choix aléatoire",
        description=f"J'ai choisi : **{chosen}**",
        color=0xff6b35
    )
    embed.add_field(name="Options", value=", ".join(choices), inline=False)
    embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@bot.command(name='quote')
async def random_quote(ctx):
    """Affiche une citation inspirante aléatoire"""
    quotes = [
        ("La vie, c'est comme une bicyclette, il faut avancer pour ne pas perdre l'équilibre.", "Albert Einstein"),
        ("Le succès, c'est tomber sept fois et se relever huit.", "Proverbe japonais"),
        ("Il n'y a que deux façons de vivre sa vie : l'une en faisant comme si rien n'était un miracle, l'autre en faisant comme si tout était un miracle.", "Albert Einstein"),
        ("L'imagination est plus importante que le savoir.", "Albert Einstein"),
        ("Hier est derrière, demain est un mystère, et aujourd'hui est un cadeau, c'est pourquoi on l'appelle le présent.", "Maître Oogway"),
        ("Ce n'est pas parce que les choses sont difficiles que nous n'osons pas, c'est parce que nous n'osons pas qu'elles sont difficiles.", "Sénèque"),
        ("La seule façon de faire du bon travail est d'aimer ce que vous faites.", "Steve Jobs"),
        ("Il vaut mieux être optimiste et se tromper qu'être pessimiste et avoir raison.", "Albert Einstein")
    ]
    
    import random
    quote, author = random.choice(quotes)
    
    embed = discord.Embed(
        title="💭 Citation du jour",
        description=f"*\"{quote}\"*",
        color=0x9932cc
    )
    embed.set_footer(text=f"— {author}")
    
    await ctx.send(embed=embed)

@bot.command(name='avatar')
async def show_avatar(ctx, member: discord.Member = None):
    """Affiche l'avatar d'un utilisateur"""
    if member is None:
        member = ctx.author
    
    embed = discord.Embed(
        title=f"🖼️ Avatar de {member.display_name}",
        color=member.color if member.color != discord.Color.default() else 0x0099ff
    )
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.set_footer(text=f"Demandé par {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

# ======================== ÉCONOMIE ========================
user_economy = {}

def get_user_economy(guild_id, user_id):
    if guild_id not in user_economy:
        user_economy[guild_id] = {}
    if user_id not in user_economy[guild_id]:
        user_economy[guild_id][user_id] = {
            "coins": 100,
            "bank": 0,
            "last_daily": None,
            "last_work": None
        }
    return user_economy[guild_id][user_id]

@bot.command(name='balance', aliases=['bal'])
async def check_balance(ctx, member: discord.Member = None):
    """Vérifie le solde d'un utilisateur"""
    if member is None:
        member = ctx.author
    
    data = get_user_economy(str(ctx.guild.id), str(member.id))
    
    embed = discord.Embed(
        title=f"💰 Portefeuille de {member.display_name}",
        color=0xffd700
    )
    embed.add_field(name="💵 En poche", value=f"{data['coins']} coins", inline=True)
    embed.add_field(name="🏦 En banque", value=f"{data['bank']} coins", inline=True)
    embed.add_field(name="💎 Total", value=f"{data['coins'] + data['bank']} coins", inline=True)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name='daily')
async def daily_reward(ctx):
    """Récupère votre récompense quotidienne"""
    data = get_user_economy(str(ctx.guild.id), str(ctx.author.id))
    now = datetime.now()
    
    if data['last_daily']:
        last_daily = datetime.fromisoformat(data['last_daily'])
        if (now - last_daily).days < 1:
            next_daily = last_daily + timedelta(days=1)
            hours_left = int((next_daily - now).total_seconds() / 3600)
            await ctx.send(f"⏰ Vous avez déjà récupéré votre récompense quotidienne ! Revenez dans {hours_left}h")
            return
    
    import random
    reward = random.randint(50, 200)
    data['coins'] += reward
    data['last_daily'] = now.isoformat()
    
    embed = discord.Embed(
        title="🎁 Récompense Quotidienne",
        description=f"Vous avez reçu **{reward} coins** !",
        color=0x00ff00
    )
    embed.add_field(name="💰 Nouveau solde", value=f"{data['coins']} coins", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='work')
async def work_command(ctx):
    """Travaillez pour gagner des coins"""
    data = get_user_economy(str(ctx.guild.id), str(ctx.author.id))
    now = datetime.now()
    
    if data['last_work']:
        last_work = datetime.fromisoformat(data['last_work'])
        if (now - last_work).total_seconds() < 3600:  # 1 heure
            minutes_left = 60 - int((now - last_work).total_seconds() / 60)
            await ctx.send(f"⏰ Vous êtes fatigué ! Reposez-vous encore {minutes_left} minutes")
            return
    
    jobs = [
        ("🍕 Livreur de pizza", 30, 80),
        ("💻 Développeur freelance", 50, 150),
        ("🎵 Musicien de rue", 20, 60),
        ("🚗 Chauffeur Uber", 40, 100),
        ("📚 Professeur particulier", 60, 120),
        ("🏪 Vendeur", 25, 70),
        ("🎨 Artiste", 35, 90),
        ("🔧 Réparateur", 45, 110)
    ]
    
    import random
    job_name, min_pay, max_pay = random.choice(jobs)
    earned = random.randint(min_pay, max_pay)
    
    data['coins'] += earned
    data['last_work'] = now.isoformat()
    
    embed = discord.Embed(
        title="💼 Travail terminé !",
        description=f"Vous avez travaillé comme {job_name}",
        color=0x0099ff
    )
    embed.add_field(name="💰 Gains", value=f"{earned} coins", inline=True)
    embed.add_field(name="💵 Nouveau solde", value=f"{data['coins']} coins", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='gamble', aliases=['bet'])
async def gamble_coins(ctx, amount: int):
    """Pariez vos coins au casino !"""
    if amount <= 0:
        await ctx.send("❌ Vous devez parier au moins 1 coin !")
        return
    
    data = get_user_economy(str(ctx.guild.id), str(ctx.author.id))
    
    if data['coins'] < amount:
        await ctx.send("❌ Vous n'avez pas assez de coins !")
        return
    
    import random
    chance = random.randint(1, 100)
    
    if chance <= 45:  # 45% de chance de gagner
        winnings = amount * 2
        data['coins'] += winnings - amount
        embed = discord.Embed(
            title="🎰 JACKPOT !",
            description=f"Vous avez gagné **{winnings} coins** !",
            color=0x00ff00
        )
    else:  # 55% de chance de perdre
        data['coins'] -= amount
        embed = discord.Embed(
            title="🎰 Perdu...",
            description=f"Vous avez perdu **{amount} coins**",
            color=0xff0000
        )
    
    embed.add_field(name="💰 Nouveau solde", value=f"{data['coins']} coins", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='give')
async def give_coins(ctx, member: discord.Member, amount: int):
    """Donnez des coins à un autre utilisateur"""
    if amount <= 0:
        await ctx.send("❌ Vous devez donner au moins 1 coin !")
        return
    
    if member == ctx.author:
        await ctx.send("❌ Vous ne pouvez pas vous donner des coins à vous-même !")
        return
    
    sender_data = get_user_economy(str(ctx.guild.id), str(ctx.author.id))
    receiver_data = get_user_economy(str(ctx.guild.id), str(member.id))
    
    if sender_data['coins'] < amount:
        await ctx.send("❌ Vous n'avez pas assez de coins !")
        return
    
    sender_data['coins'] -= amount
    receiver_data['coins'] += amount
    
    embed = discord.Embed(
        title="💸 Transaction effectuée",
        description=f"{ctx.author.mention} a donné **{amount} coins** à {member.mention}",
        color=0x00ff00
    )
    
    await ctx.send(embed=embed)

# ======================== MINI-JEUX ========================

@bot.command(name='rps')
async def rock_paper_scissors(ctx, choice=None):
    """Pierre-papier-ciseaux contre le bot"""
    if not choice or choice.lower() not in ['pierre', 'papier', 'ciseaux', 'rock', 'paper', 'scissors']:
        await ctx.send("❌ Choisissez: `pierre`, `papier`, ou `ciseaux`")
        return
    
    # Normaliser les choix
    choices_map = {
        'pierre': 'pierre', 'rock': 'pierre',
        'papier': 'papier', 'paper': 'papier',
        'ciseaux': 'ciseaux', 'scissors': 'ciseaux'
    }
    
    user_choice = choices_map[choice.lower()]
    
    import random
    bot_choices = ['pierre', 'papier', 'ciseaux']
    bot_choice = random.choice(bot_choices)
    
    emojis = {'pierre': '🪨', 'papier': '📄', 'ciseaux': '✂️'}
    
    # Déterminer le gagnant
    if user_choice == bot_choice:
        result = "🤝 Égalité !"
        color = 0xffff00
    elif (user_choice == 'pierre' and bot_choice == 'ciseaux') or \
         (user_choice == 'papier' and bot_choice == 'pierre') or \
         (user_choice == 'ciseaux' and bot_choice == 'papier'):
        result = "🎉 Vous gagnez !"
        color = 0x00ff00
        # Donner une récompense
        data = get_user_economy(str(ctx.guild.id), str(ctx.author.id))
        data['coins'] += 10
    else:
        result = "😢 Vous perdez !"
        color = 0xff0000
    
    embed = discord.Embed(
        title="🪨📄✂️ Pierre-Papier-Ciseaux",
        description=result,
        color=color
    )
    embed.add_field(name="Votre choix", value=f"{emojis[user_choice]} {user_choice.title()}", inline=True)
    embed.add_field(name="Mon choix", value=f"{emojis[bot_choice]} {bot_choice.title()}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='memory')
async def memory_game(ctx):
    """Jeu de mémoire - répétez la séquence"""
    import random
    
    sequence = []
    emojis = ['🔴', '🟡', '🟢', '🔵', '🟣']
    
    for round_num in range(1, 6):  # 5 rounds
        # Ajouter un nouvel emoji à la séquence
        sequence.append(random.choice(emojis))
        
        # Afficher la séquence
        embed = discord.Embed(
            title=f"🧠 Jeu de Mémoire - Round {round_num}",
            description="Mémorisez cette séquence :",
            color=0x9932cc
        )
        embed.add_field(name="Séquence", value=" ".join(sequence), inline=False)
        embed.add_field(name="Instructions", value="Répondez avec les emojis dans l'ordre !", inline=False)
        
        message = await ctx.send(embed=embed)
        
        # Attendre la réponse
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        try:
            response = await bot.wait_for('message', check=check, timeout=30.0)
            user_sequence = response.content.split()
            
            if user_sequence == sequence:
                if round_num == 5:  # Dernière manche
                    reward = 100
                    data = get_user_economy(str(ctx.guild.id), str(ctx.author.id))
                    data['coins'] += reward
                    
                    embed = discord.Embed(
                        title="🎉 PARFAIT !",
                        description=f"Vous avez terminé tous les rounds ! +{reward} coins",
                        color=0x00ff00
                    )
                    await ctx.send(embed=embed)
                    return
                else:
                    await ctx.send(f"✅ Correct ! Round {round_num + 1}...")
                    await asyncio.sleep(2)
            else:
                embed = discord.Embed(
                    title="❌ Incorrect !",
                    description=f"Vous avez échoué au round {round_num}",
                    color=0xff0000
                )
                embed.add_field(name="Bonne réponse", value=" ".join(sequence), inline=False)
                await ctx.send(embed=embed)
                return
                
        except asyncio.TimeoutError:
            await ctx.send("⏰ Temps écoulé ! Jeu terminé.")
            return

@bot.command(name='guess')
async def number_guessing(ctx, number: int = None):
    """Devinez le nombre entre 1 et 100"""
    if number is None:
        await ctx.send("❌ Choisissez un nombre ! Exemple: `!guess 50`")
        return
    
    if number < 1 or number > 100:
        await ctx.send("❌ Le nombre doit être entre 1 et 100 !")
        return
    
    import random
    secret_number = random.randint(1, 100)
    
    if number == secret_number:
        reward = 50
        data = get_user_economy(str(ctx.guild.id), str(ctx.author.id))
        data['coins'] += reward
        
        embed = discord.Embed(
            title="🎯 BRAVO !",
            description=f"Vous avez trouvé le nombre {secret_number} !",
            color=0x00ff00
        )
        embed.add_field(name="🎁 Récompense", value=f"+{reward} coins", inline=True)
    else:
        distance = abs(number - secret_number)
        if distance <= 5:
            message = "🔥 Très proche !"
        elif distance <= 15:
            message = "😊 Proche !"
        elif distance <= 30:
            message = "🤔 Assez loin..."
        else:
            message = "❄️ Très loin !"
        
        embed = discord.Embed(
            title="❌ Raté !",
            description=f"Le nombre était {secret_number}",
            color=0xff0000
        )
        embed.add_field(name="Votre nombre", value=str(number), inline=True)
        embed.add_field(name="Distance", value=message, inline=True)
    
    await ctx.send(embed=embed)

# ======================== UTILITAIRES ========================

@bot.command(name='calc')
async def calculator(ctx, *, expression):
    """Calculatrice simple"""
    try:
        # Sécurité basique
        allowed_chars = "0123456789+-*/(). "
        if not all(char in allowed_chars for char in expression):
            await ctx.send("❌ Caractères non autorisés ! Utilisez seulement: + - * / ( ) et des nombres")
            return
        
        result = eval(expression)
        
        embed = discord.Embed(
            title="🧮 Calculatrice",
            color=0x0099ff
        )
        embed.add_field(name="Expression", value=f"`{expression}`", inline=False)
        embed.add_field(name="Résultat", value=f"**{result}**", inline=False)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Erreur dans l'expression : {str(e)}")

@bot.command(name='translate')
async def translate_text(ctx, target_lang, *, text):
    """Traduction simple (simulation)"""
    translations = {
        'en': {
            'bonjour': 'hello',
            'au revoir': 'goodbye',
            'merci': 'thank you',
            'oui': 'yes',
            'non': 'no',
            'chat': 'cat',
            'chien': 'dog',
            'maison': 'house',
            'voiture': 'car'
        },
        'es': {
            'bonjour': 'hola',
            'au revoir': 'adiós',
            'merci': 'gracias',
            'oui': 'sí',
            'non': 'no',
            'chat': 'gato',
            'chien': 'perro',
            'maison': 'casa',
            'voiture': 'coche'
        }
    }
    
    if target_lang not in ['en', 'es']:
        await ctx.send("❌ Langues supportées: `en` (anglais), `es` (espagnol)")
        return
    
    text_lower = text.lower()
    translated = translations[target_lang].get(text_lower, f"[Traduction non disponible pour '{text}']")
    
    embed = discord.Embed(
        title="🌍 Traducteur",
        color=0x00aaff
    )
    embed.add_field(name="Texte original", value=text, inline=False)
    embed.add_field(name=f"Traduction ({target_lang})", value=translated, inline=False)
    embed.set_footer(text="Traducteur basique - mots simples uniquement")
    
    await ctx.send(embed=embed)

@bot.command(name='weather')
async def fake_weather(ctx, *, city="Paris"):
    """Météo simulée"""
    import random
    
    weather_conditions = [
        ("☀️", "Ensoleillé", 0xffd700),
        ("⛅", "Partiellement nuageux", 0x87ceeb),
        ("☁️", "Nuageux", 0x696969),
        ("🌧️", "Pluvieux", 0x4682b4),
        ("⛈️", "Orageux", 0x483d8b),
        ("❄️", "Neigeux", 0xf0f8ff)
    ]
    
    emoji, condition, color = random.choice(weather_conditions)
    temperature = random.randint(-5, 35)
    humidity = random.randint(30, 90)
    wind_speed = random.randint(5, 25)
    
    embed = discord.Embed(
        title=f"{emoji} Météo à {city}",
        description=condition,
        color=color
    )
    embed.add_field(name="🌡️ Température", value=f"{temperature}°C", inline=True)
    embed.add_field(name="💧 Humidité", value=f"{humidity}%", inline=True)
    embed.add_field(name="💨 Vent", value=f"{wind_speed} km/h", inline=True)
    embed.set_footer(text="⚠️ Données météo simulées pour le divertissement")
    
    await ctx.send(embed=embed)

@bot.command(name='qr')
async def qr_code_info(ctx, *, text):
    """Génère un lien QR code"""
    import urllib.parse
    
    encoded_text = urllib.parse.quote(text)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={encoded_text}"
    
    embed = discord.Embed(
        title="📱 Code QR",
        description=f"QR Code pour: **{text}**",
        color=0x000000
    )
    embed.set_image(url=qr_url)
    embed.add_field(name="💡 Info", value="Scannez ce code avec votre téléphone", inline=False)
    
    await ctx.send(embed=embed)

# ======================== RÔLES AUTOMATIQUES ========================

@bot.command(name='autorole')
async def setup_autorole(ctx, role: discord.Role):
    """Configure un rôle automatique pour les nouveaux membres"""
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ Vous n'avez pas la permission de gérer les rôles !")
        return
    
    guild_id = str(ctx.guild.id)
    if guild_id not in guild_settings:
        guild_settings[guild_id] = {}
    
    guild_settings[guild_id]["autorole"] = role.id
    
    embed = discord.Embed(
        title="✅ Rôle automatique configuré",
        description=f"Les nouveaux membres recevront automatiquement le rôle {role.mention}",
        color=0x00ff00
    )
    
    await ctx.send(embed=embed)

# ======================== ANNIVERSAIRES ========================
user_birthdays = {}

@bot.command(name='birthday')
async def set_birthday(ctx, date=None):
    """Définir votre date d'anniversaire (format: JJ/MM)"""
    if not date:
        await ctx.send("❌ Format: `!birthday 15/03` (jour/mois)")
        return
    
    try:
        day, month = map(int, date.split('/'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError
        
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if guild_id not in user_birthdays:
            user_birthdays[guild_id] = {}
        
        user_birthdays[guild_id][user_id] = f"{day:02d}/{month:02d}"
        
        embed = discord.Embed(
            title="🎂 Anniversaire enregistré !",
            description=f"Votre anniversaire a été défini au {day:02d}/{month:02d}",
            color=0xff69b4
        )
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Format invalide ! Utilisez: JJ/MM (ex: 15/03)")

@bot.command(name='birthdays')
async def list_birthdays(ctx):
    """Liste des anniversaires du serveur"""
    guild_id = str(ctx.guild.id)
    
    if guild_id not in user_birthdays or not user_birthdays[guild_id]:
        await ctx.send("📅 Aucun anniversaire enregistré sur ce serveur.")
        return
    
    embed = discord.Embed(
        title="🎂 Anniversaires du serveur",
        color=0xff69b4
    )
    
    for user_id, birthday in user_birthdays[guild_id].items():
        member = ctx.guild.get_member(int(user_id))
        if member:
            embed.add_field(
                name=member.display_name,
                value=f"🎂 {birthday}",
                inline=True
            )
    
    await ctx.send(embed=embed)

# ======================== SYSTÈME DM ALL ========================

@bot.command(name='dmall')
async def dm_all_members(ctx, *, message=None):
    """Envoie un message privé à tous les membres du serveur"""
    # Vérifier les permissions
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Seuls les administrateurs peuvent utiliser cette commande!")
        return
    
    if not message:
        await ctx.send("❌ Veuillez spécifier un message ! Exemple: `!dmall Bonjour tout le monde !`")
        return
    
    # Confirmation
    embed = discord.Embed(
        title="⚠️ Confirmation DM All",
        description=f"Êtes-vous sûr de vouloir envoyer ce message à **{len([m for m in ctx.guild.members if not m.bot])}** membres ?",
        color=0xffa500
    )
    embed.add_field(name="📝 Message", value=message, inline=False)
    embed.add_field(name="✅ Confirmation", value="Réagissez avec ✅ pour confirmer\n❌ pour annuler", inline=False)
    
    confirm_msg = await ctx.send(embed=embed)
    await confirm_msg.add_reaction("✅")
    await confirm_msg.add_reaction("❌")
    
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
    
    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
        
        if str(reaction.emoji) == "❌":
            await ctx.send("❌ Envoi de masse annulé.")
            return
        
        # Commencer l'envoi
        status_embed = discord.Embed(
            title="📨 Envoi en cours...",
            description="Début de l'envoi des messages privés",
            color=0x0099ff
        )
        status_msg = await ctx.send(embed=status_embed)
        
        success_count = 0
        failed_count = 0
        members = [member for member in ctx.guild.members if not member.bot]
        
        # Créer l'embed du message
        dm_embed = discord.Embed(
            title=f"📢 Message de {ctx.guild.name}",
            description=message,
            color=0x00ff00
        )
        dm_embed.set_footer(text=f"Envoyé par {ctx.author.display_name} • {ctx.guild.name}")
        dm_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        for i, member in enumerate(members):
            try:
                await member.send(embed=dm_embed)
                success_count += 1
            except discord.Forbidden:
                failed_count += 1
            except discord.HTTPException:
                failed_count += 1
            
            # Mettre à jour le statut toutes les 10 envois
            if (i + 1) % 10 == 0 or i == len(members) - 1:
                progress = int((i + 1) / len(members) * 100)
                status_embed.description = f"Progression: {i + 1}/{len(members)} ({progress}%)\n✅ Succès: {success_count}\n❌ Échecs: {failed_count}"
                await status_msg.edit(embed=status_embed)
            
            # Délai pour éviter le spam
            await asyncio.sleep(1)
        
        # Résultat final
        final_embed = discord.Embed(
            title="📨 Envoi terminé !",
            color=0x00ff00 if failed_count == 0 else 0xffa500
        )
        final_embed.add_field(name="✅ Messages envoyés", value=str(success_count), inline=True)
        final_embed.add_field(name="❌ Échecs", value=str(failed_count), inline=True)
        final_embed.add_field(name="📊 Total", value=str(len(members)), inline=True)
        
        if failed_count > 0:
            final_embed.add_field(
                name="💡 Note",
                value="Certains membres ont leurs DM fermés ou bloquent le bot.",
                inline=False
            )
        
        await status_msg.edit(embed=final_embed)
        
    except asyncio.TimeoutError:
        await ctx.send("⏰ Temps de confirmation écoulé. Envoi annulé.")

@bot.command(name='dmuser')
async def dm_specific_user(ctx, member: discord.Member, *, message):
    """Envoie un message privé à un utilisateur spécifique"""
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("❌ Vous n'avez pas la permission d'utiliser cette commande!")
        return
    
    if member.bot:
        await ctx.send("❌ Impossible d'envoyer un message à un bot!")
        return
    
    try:
        dm_embed = discord.Embed(
            title=f"📩 Message de {ctx.guild.name}",
            description=message,
            color=0x0099ff
        )
        dm_embed.set_footer(text=f"Envoyé par {ctx.author.display_name} via le bot")
        
        await member.send(embed=dm_embed)
        await ctx.send(f"✅ Message envoyé à {member.mention}")
        
    except discord.Forbidden:
        await ctx.send(f"❌ {member.mention} a ses DM fermés ou me bloque!")
    except discord.HTTPException:
        await ctx.send("❌ Erreur lors de l'envoi du message!")

@bot.command(name='announce')
async def make_announcement(ctx, channel: discord.TextChannel, *, message):
    """Fait une annonce officielle dans un salon"""
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("❌ Vous n'avez pas la permission de faire des annonces!")
        return
    
    embed = discord.Embed(
        title="📢 ANNONCE OFFICIELLE",
        description=message,
        color=0xff0000
    )
    embed.set_author(
        name=ctx.author.display_name,
        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
    )
    embed.set_footer(text=f"Serveur: {ctx.guild.name}")
    embed.timestamp = datetime.now()
    
    try:
        announce_msg = await channel.send("@everyone", embed=embed)
        await announce_msg.add_reaction("📌")
        await ctx.send(f"✅ Annonce publiée dans {channel.mention}")
    except discord.Forbidden:
        await ctx.send(f"❌ Pas de permission pour écrire dans {channel.mention}!")

# ======================== GESTION DE MUSIQUE BASIQUE ========================

@bot.command(name='music')
async def music_help(ctx):
    """Guide pour la musique"""
    embed = discord.Embed(
        title="🎵 Système Musical",
        description="Commandes musicales disponibles :",
        color=0x9932cc
    )
    
    embed.add_field(
        name="🎶 Commandes",
        value="`!play <lien>` - Jouer de la musique\n`!stop` - Arrêter la musique\n`!volume <1-100>` - Changer le volume",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Prérequis",
        value="• Le bot doit être dans un salon vocal\n• Vous devez être dans le même salon\n• Permissions nécessaires",
        inline=False
    )
    
    embed.add_field(
        name="💡 Info",
        value="Pour une expérience musicale complète, des packages supplémentaires sont nécessaires.",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ======================== SYSTÈME DE RÉPUTATIONS ========================
user_reputation = {}

@bot.command(name='rep')
async def give_reputation(ctx, member: discord.Member, *, reason=None):
    """Donner une réputation positive à un membre"""
    if member == ctx.author:
        await ctx.send("❌ Vous ne pouvez pas vous donner de la réputation !")
        return
    
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    giver_id = str(ctx.author.id)
    
    if guild_id not in user_reputation:
        user_reputation[guild_id] = {}
    
    if user_id not in user_reputation[guild_id]:
        user_reputation[guild_id][user_id] = {"positive": 0, "negative": 0, "given_by": []}
    
    # Vérifier si déjà donné
    if giver_id in user_reputation[guild_id][user_id]["given_by"]:
        await ctx.send("❌ Vous avez déjà donné votre réputation à ce membre !")
        return
    
    user_reputation[guild_id][user_id]["positive"] += 1
    user_reputation[guild_id][user_id]["given_by"].append(giver_id)
    
    embed = discord.Embed(
        title="⭐ Réputation donnée !",
        description=f"{member.mention} a reçu +1 réputation de {ctx.author.mention}",
        color=0x00ff00
    )
    
    if reason:
        embed.add_field(name="Raison", value=reason, inline=False)
    
    total_rep = user_reputation[guild_id][user_id]["positive"] - user_reputation[guild_id][user_id]["negative"]
    embed.add_field(name="Réputation totale", value=f"⭐ {total_rep}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='reputation')
async def check_reputation(ctx, member: discord.Member = None):
    """Vérifier la réputation d'un membre"""
    if member is None:
        member = ctx.author
    
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    if guild_id not in user_reputation or user_id not in user_reputation[guild_id]:
        await ctx.send(f"{member.mention} n'a pas encore de réputation.")
        return
    
    data = user_reputation[guild_id][user_id]
    total_rep = data["positive"] - data["negative"]
    
    embed = discord.Embed(
        title=f"⭐ Réputation de {member.display_name}",
        color=0xffd700 if total_rep >= 0 else 0xff0000
    )
    
    embed.add_field(name="👍 Positive", value=str(data["positive"]), inline=True)
    embed.add_field(name="👎 Négative", value=str(data["negative"]), inline=True)
    embed.add_field(name="📊 Total", value=str(total_rep), inline=True)
    
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    
    await ctx.send(embed=embed)

# Système de tickets
@bot.command(name='ticket')
async def create_ticket(ctx):
    category = discord.utils.get(ctx.guild.categories, name="🎫 TICKETS")
    if not category:
        try:
            category = await ctx.guild.create_category("🎫 TICKETS")
        except discord.Forbidden:
            await ctx.send("❌ Je n'ai pas la permission de créer des catégories!")
            return

    ticket_name = f"ticket-{ctx.author.name}"
    existing_ticket = discord.utils.get(ctx.guild.channels, name=ticket_name)
    if existing_ticket:
        await ctx.send(f"❌ Vous avez déjà un ticket ouvert: {existing_ticket.mention}")
        return

    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    try:
        ticket_channel = await ctx.guild.create_text_channel(
            ticket_name,
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎫 Nouveau Ticket",
            description=f"Bonjour {ctx.author.mention}!\n\nDécrivez votre problème ou votre demande. Un membre du staff vous répondra bientôt.\n\nPour fermer ce ticket, tapez `!close`",
            color=0x00ff00
        )
        await ticket_channel.send(embed=embed)
        await ctx.send(f"✅ Ticket créé: {ticket_channel.mention}")

    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de créer des salons!")
    except discord.HTTPException:
        await ctx.send("❌ Erreur lors de la création du ticket!")

@bot.command(name='close')
async def close_ticket(ctx):
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ Cette commande ne peut être utilisée que dans un salon de ticket!")
        return

    ticket_owner_name = ctx.channel.name.replace("ticket-", "")
    is_ticket_owner = ctx.author.name == ticket_owner_name
    has_manage_channels = ctx.author.guild_permissions.manage_channels

    if not (is_ticket_owner or has_manage_channels):
        await ctx.send("❌ Seul le créateur du ticket ou un membre du staff peut fermer ce ticket!")
        return

    embed = discord.Embed(
        title="🔒 Fermeture du Ticket",
        description="Ce ticket sera supprimé dans 5 secondes...",
        color=0xff0000
    )
    await ctx.send(embed=embed)

    await asyncio.sleep(5)

    try:
        await ctx.channel.delete()
    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas la permission de supprimer ce salon!")
    except discord.HTTPException:
        await ctx.send("❌ Erreur lors de la suppression du ticket!")

@bot.event
async def on_ready():
    print(f'Bot connecté en tant que {bot.user}')

@bot.event
async def on_ready():
    print(f'Bot connecté en tant que {bot.user}')
    print('En attente de messages...')

token = os.environ['TOKENBOT']
bot.run(token)
