import discord
from discord.ext import commands
import random
import string
import json
import asyncio
import datetime

intents = discord.Intents.all()
currenttime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
bot = commands.Bot(command_prefix='.', intents=intents)

# Set the log channel ID
payment_channel_id = 1234567890


def load_payments():
    try:
        with open('payments.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

    except json.JSONDecodeError:
        return {}

def save_payments(payments):
    payments_copy = {}
    for user_id, data in payments.items():
        payments_copy[user_id] = {
            'order_id': data['order_id'],
            'amount': data['amount'],
            'status': data['status'],
            'user_id': data['user_id'],
            'payment_method': data.get('payment_method'),
            'paysafecard_code': data.get('paysafecard_code'),
            'confirmation_time': data.get('confirmation_time'),
            'created': currenttime 
        }

    with open('payments.json', 'w') as file:
        json.dump(payments_copy, file, indent=4)


def has_required_role(ctx):
    required_role_id = 1234567890 # ID  of the main permission role
    required_role = ctx.guild.get_role(required_role_id)
    return required_role in ctx.author.roles

payments = load_payments()

def load_blacklist():
    try:
        with open('blacklist.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

def save_blacklist(blacklist):
    with open('blacklist.json', 'w') as file:
        json.dump(blacklist, file, indent=4)

blacklist = load_blacklist()


def is_blacklisted(user):
    return user.id in blacklist



@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Payment Control"))
    print(f'Bot is ready. Logged in as {bot.user}')

@bot.command()
async def pay(ctx, user: discord.User, amount: int):
    load_payments()
    global order_number
    payment_channel = bot.get_channel(payment_channel_id)

    try:
        user = await bot.fetch_user(user.id)
    except discord.NotFound:
        await ctx.send('The specified user was not found.')
        return

    if user.id in payments and payments[user.id]['status'] in ['Pending', 'Banned']:
        order_id = payments[user.id]['order_id']
        status = payments[user.id]['status']

        embed = discord.Embed(
            title='Payment Status',
            description=f'Your previous order with Order ID {order_id} is {status}. You cant place a new order even if you have a pending or banned payment / account.',
            color=0x00ff00
        )
        await ctx.send(embed=embed)
        return

    order_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    order_id = f'FS-{order_number}'
    while order_id in payments:
        order_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        order_id = f'FS-{order_number}'

    payment_method = None
    emoji_paysafecard = '🔒'

    if user.id not in payments:
        payments[user.id] = {}

    payments[user.id]['order_id'] = order_id
    payments[user.id]['amount'] = amount
    payments[user.id]['status'] = 'Pending'
    payments[user.id]['user_id'] = user.id

    payment_embed = discord.Embed(
        title='**Payment Request**',
        description=f'You have received a payment request for {amount} EUR. Please choose a payment method or use ***.exit*** to exit:',
        color=0x00FF00  # Green
    )
    payment_embed.add_field(name='Payment Method', value=':regional_indicator_p: PayPal\n:lock: Paysafecard\n:regional_indicator_c: Cryptocurrency', inline=False)

    payment_message = await user.send(embed=payment_embed)

    await payment_message.add_reaction('🇵')
    await payment_message.add_reaction(emoji_paysafecard)
    await payment_message.add_reaction('🇨')

    def check(reaction, reactor):
        return reactor.id == user.id and str(reaction.emoji) in ['🇵', emoji_paysafecard, '🇨']

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        embed = discord.Embed(
            title='Payment Timed Out',
            description='You did not select a payment method. The payment has been canceled.',
            color=0xFF0000  # red
        )
        await user.send(embed=embed)
        return
    else:
        if str(reaction.emoji) == '🇵':
            payment_method = 'PayPal'
            paypal_embed = discord.Embed(
                title='Pay with PayPal',
                description=f'Send the amount of ***{amount} EUR*** to the PayPal email address: your-paypal-email@example.com.\nAnd add the order id into the comment / Text: {order_id}.',
                color=0x00FF00  # Green
            )
            await user.send(embed=paypal_embed)

            payment_channel_embed = discord.Embed(
                title='**Payment Information**',
                description='Payment details:',
                color=0x00FF00  # Green
            )
            payment_channel_embed.add_field(name='Order Number', value=order_id, inline=False)
            payment_channel_embed.add_field(name='User', value=user.mention, inline=False)
            payment_channel_embed.add_field(name='Amount', value=f'{amount} EUR', inline=False)
            payment_channel_embed.add_field(name='Payment Method', value=payment_method, inline=False)
            payment_channel_embed.add_field(name='Time', value=currenttime, inline=False)
            await payment_channel.send(embed=payment_channel_embed)

            log_message = f'Payment with order number {order_id} initiated by {user.mention} using PayPal.[- {currenttime} ] Please validate and Confirm !'
            await payment_channel.send(log_message)
        elif str(reaction.emoji) == emoji_paysafecard:
            payment_method = 'Paysafecard'
            await user.send('Please enter the Paysafecard code:')
            try:
                paysafecard_code = await bot.wait_for('message', timeout=60.0, check=lambda message: message.author == user)
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title='Payment Timed Out',
                    description='You did not enter a Paysafecard code. The payment has been canceled.',
                    color=0xFF0000  # red
                )
                await user.send(embed=embed)
                return
            payments[user.id]['paysafecard_code'] = paysafecard_code.content

            payment_channel_embed = discord.Embed(
                title='**Payment Information**',
                description='Payment details:',
                color=0x00FF00  # Green
            )
            payment_channel_embed.add_field(name='Order Number', value=order_id, inline=False)
            payment_channel_embed.add_field(name='User', value=user.mention, inline=False)
            payment_channel_embed.add_field(name='Amount', value=f'{amount} EUR', inline=False)
            payment_channel_embed.add_field(name='Payment Method', value=payment_method, inline=False)
            payment_channel_embed.add_field(name='Paysafecard Code', value=paysafecard_code.content, inline=False)
            payment_channel_embed.add_field(name='Time', value=currenttime, inline=False)
            await payment_channel.send(embed=payment_channel_embed)

            log_message = f'Payment with order number {order_id} initiated by {user.mention} using Paysafecard.[- {currenttime} ] Please validate and Confirm !'
            await payment_channel.send(log_message)
        elif str(reaction.emoji) == '🇨':
            payment_method = 'Cryptocurrency'
            log_message = f'Payment with order number {order_id} initiated by {user.mention} using Cryptocurrency.[- {currenttime} ] Please validate and Confirm !'
            await payment_channel.send(log_message)

            crypto_embed = discord.Embed(
                title='Cryptocurrency Payments',
                description='Cryptocurrency payments are currently not available. The payment has been canceled.',
                color=0xFF0000  # red
            )
            await user.send(embed=crypto_embed)


            log_message = f'Payment with order number {order_id} Stopped {user.mention} Because Crypto not accepable atm.- {currenttime}'
            await payment_channel.send(log_message)
            return
        else:
            embed = discord.Embed(
                title='Invalid Reaction',
                description='Invalid reaction. The payment has been canceled.',
                color=0xFF0000  # red
            )
            await user.send(embed=embed)
            payments[user.id]['status'] = 'Canceled'  # Set status to canceled 'Canceled'
            save_payments(payments)
            return

        payments[user.id]['payment_method'] = payment_method
        save_payments(payments)


        success_embed = discord.Embed(
            title='Payment Registered',
            description=f'Your payment has been successfully registered. Order Number: {order_id}',
            color=0x00FF00  # Green
        )
        await user.send(embed=success_embed)


@bot.command()
@commands.check(has_required_role)
async def confirm(ctx, user: discord.User):
    payment_channel = bot.get_channel(payment_channel_id)

    if user.id in payments and payments[user.id]['status'] != 'Canceled':  # Check if canceled
        order_id = payments[user.id]['order_id']
        payments[user.id]['status'] = 'Confirmed'
        payments[user.id]['confirmation_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_payments(payments)

        payment_channel_embed = discord.Embed(
            title='Payment Confirmed',
            description=f'Payment with order number {order_id} has been confirmed by {ctx.author.mention} at {payments[user.id]["confirmation_time"]}.',
            color=0x00FF00  # Green
        )
        await payment_channel.send(embed=payment_channel_embed)

        user_id = payments[user.id]['user_id']
        user = await bot.fetch_user(user_id)

        user_embed = discord.Embed(
            title='Payment Confirmed',
            description=f'Your payment has been confirmed by {ctx.author.mention} at {payments[user.id]["confirmation_time"]}.',
            color=0x00FF00  # Green
        )
        await user.send(embed=user_embed)
    else:
        embed = discord.Embed(
            title='Invalid Payment',
            description='Invalid order number or payment already canceled.',
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)


@bot.command()
async def exit(ctx):
    payment_channel = bot.get_channel(payment_channel_id)

    if ctx.author.id in payments:
        order_id = payments[ctx.author.id]['order_id']
        payments[ctx.author.id]['status'] = 'Canceled'  # Set canceled
        save_payments(payments)

        payment_channel_embed = discord.Embed(
            title='Payment Canceled',
            description=f'Payment with order number {order_id} has been canceled by {ctx.author.mention} at {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.',
            color=0xFF0000  # red
        )
        await payment_channel.send(embed=payment_channel_embed)

        del payments[ctx.author.id]

        user_embed = discord.Embed(
            title='Payment Canceled',
            description='Your payment has been canceled.',
            color=0x00FF00  # Green
        )
        await ctx.send(embed=user_embed)
    else:
        embed = discord.Embed(
            title='No Pending Payment',
            description="You do not have a pending payment.",
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)



@bot.command()
@commands.check(has_required_role)
async def plist(ctx):
    payment_channel = bot.get_channel(payment_channel_id)

    if not payments:
        await ctx.send('**There are no pending payments.**')
        return

    embed = discord.Embed(title='Payment List', color=0x00ff00)  

    for data in payments.values():
        order_id = data['order_id']
        user = bot.get_user(data['user_id']).mention
        amount = data['amount']
        status = data['status']
        
        embed.add_field(name='Order ID', value=order_id, inline=True)
        embed.add_field(name='User', value=user, inline=True)
        embed.add_field(name='Amount', value=f'{amount} EUR', inline=True)
        embed.add_field(name='Status', value=status, inline=True)

    await ctx.send(embed=embed)  


blacklist = []  

@bot.command()
@commands.check(has_required_role)
async def pblacklist(ctx, user: discord.User):
    if user.id not in blacklist:
        blacklist.append(user.id) 
        save_blacklist(blacklist)

        embed = discord.Embed(
            title='User Blacklisted',
            description=f'{user.mention} has been blacklisted.',
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)
    else:

        embed = discord.Embed(
            title='Already Blacklisted',
            description=f'{user.mention} is already blacklisted.',
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)

@bot.command()
@commands.check(has_required_role)
async def punblacklist(ctx, user: discord.User):
    if user.id in blacklist:
        blacklist.remove(user.id)  
        save_blacklist(blacklist)
        embed = discord.Embed(
            title='User Removed from Blacklist',
            description=f'{user.mention} has been removed from the blacklist.',
            color=0x00FF00  # Green
        )
        await ctx.send(embed=embed)
    else:

        embed = discord.Embed(
            title='Not in Blacklist',
            description=f'{user.mention} is not in the blacklist.',
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)

@bot.command()
@commands.check(has_required_role)
async def pinfo(ctx, user: discord.User):

    is_blacklisted = user.id in blacklist


    user_payments = [data for data in payments.values() if data['user_id'] == user.id]

    embed = discord.Embed(
        title=f'User Information for {user}',
        color=0x00ff00 if not is_blacklisted else 0xff0000  
    )

    embed.add_field(name='Blacklisted', value='Yes' if is_blacklisted else 'No', inline=False)
    
    if user_payments:
        embed.add_field(name='Payments Made', value='\n'.join([f'Order ID: {data["order_id"]} | Amount: {data["amount"]} EUR | Status: {data["status"]}' for data in user_payments]), inline=False)
    else:
        embed.add_field(name='Payments Made', value='No payments made by this user.')

    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing required arguments. Please check the command usage.")
    else:

        error_embed = discord.Embed(
            title="An Error Occurred",
            description=f"An error occurred while executing the command: `{ctx.command}`\n\nError Details: {error}",
            color=0xFF0000  # red
        )
        await ctx.send(embed=error_embed)


@bot.command()
@commands.check(has_required_role)
async def payinfo(ctx, order_number: str):

    if order_number not in [data['order_id'] for data in payments.values()]:
        await ctx.send(f'Order number {order_number} not found.')
        return


    payment_data = next(data for data in payments.values() if data['order_id'] == order_number)


    payment_info_embed = discord.Embed(
        title=f'Payment Information for Order Number: {order_number}',
        description=f'Payment Status: {payment_data["status"]}',
        color=0x00ff00  
    )
    payment_info_embed.add_field(name='User', value=bot.get_user(payment_data['user_id']).mention, inline=False)
    payment_info_embed.add_field(name='Amount', value=f'{payment_data["amount"]} EUR', inline=False)
    payment_info_embed.add_field(name='Payment Method', value=payment_data.get('payment_method', 'N/A'), inline=False)
    payment_info_embed.add_field(name='Paysafecard Code', value=payment_data.get('paysafecard_code', 'N/A'), inline=False)
    payment_info_embed.add_field(name='Confirmation Time', value=payment_data.get('confirmation_time', 'N/A'), inline=False)
    payment_info_embed.add_field(name='Created', value=payment_data.get('created', 'N/A'), inline=False)

    await ctx.send(embed=payment_info_embed)


@bot.command()
@commands.check(has_required_role)  
async def pwarning(ctx, order_id: str):
    payment_channel = bot.get_channel(payment_channel_id)

    if order_id in [data['order_id'] for data in payments.values()]:
        for user_id, data in payments.items():
            if data['order_id'] == order_id:
                user = await bot.fetch_user(user_id)
                data['status'] = 'Pending Verification'  
                save_payments(payments)

                embed = discord.Embed(
                    title='Order Under Suspicion',
                    description=f'Your order with order number {order_id} is currently under suspicion and is being reviewed for potential fraud.',
                    color=0xFF0000  # red
                )
                await user.send(embed=embed)
                await ctx.send(f'Order with order number {order_id} is under suspicion and is being reviewed for potential fraud.')
                return

    await ctx.send('The specified order number was not found or is already completed.')


@bot.command()
@commands.check(has_required_role)
async def pdecline(ctx, order_id):
    if order_id in payments:
        payments[order_id]['status'] = 'Declined'
        save_payments(payments)

        
        embed = discord.Embed(
            title='Payment Declined',
            description=f'Payment with order number {order_id} has been declined.',
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)
    else:
        
        embed = discord.Embed(
            title='Invalid Order Number',
            description=f'Order number {order_id} is invalid or does not exist.',
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)

@bot.command()
@commands.check(has_required_role)
async def psetamount(ctx, order_id, new_amount):
    if order_id in payments:
        payments[order_id]['amount'] = new_amount
        save_payments(payments)

       
        embed = discord.Embed(
            title='Amount Updated',
            description=f'Amount for payment with order number {order_id} has been updated to {new_amount} EUR.',
            color=0x00FF00  # Green
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title='Invalid Order Number',
            description=f'Order number {order_id} is invalid or does not exist.',
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)

@bot.command()
@commands.check(has_required_role)
async def psetmethod(ctx, order_id, new_method):
    valid_methods = ['PayPal', 'Paysafecard', 'Cryptocurrency']

    if order_id in payments:
        if new_method in valid_methods:
            payments[order_id]['payment_method'] = new_method
            save_payments(payments)


            embed = discord.Embed(
                title='Payment Method Updated',
                description=f'Payment method for order number {order_id} has been updated to {new_method}.',
                color=0x00FF00  # Green
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title='Invalid Payment Method',
                description=f'{new_method} is not a valid payment method. Please use one of the following: {", ".join(valid_methods)}',
                color=0xFF0000  # red
            )
            await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title='Invalid Order Number',
            description=f'Order number {order_id} is invalid or does not exist.',
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)


@bot.command()
async def phelp(ctx):
    embed = discord.Embed(
        title='Command List',
        description='List of available commands:',
        color=0x00FF00  # Green
    )

    embed.add_field(name='.pay (user) (betrag)', value='Initiate a payment request.', inline=False)
    embed.add_field(name='.plist', value='List all pending payments.', inline=False)
    embed.add_field(name='.pinfo (order_id)', value='Get information about a specific payment.', inline=False)
    embed.add_field(name='.pblacklist (user)', value='Blacklist a user from using the payment system.', inline=False)
    embed.add_field(name='.punblacklist (user)', value='Remove a user from the blacklist.', inline=False)
    embed.add_field(name='.pwarning (order_id)', value='Set the status of a payment to "Under Review".', inline=False)
    embed.add_field(name='.psetmethod (order_id) (payment_method)', value='Update the payment method for an order.', inline=False)
    embed.add_field(name='.pdecline (order_id)', value='Decline a pending payment request.', inline=False)
    embed.add_field(name='.setamount (order_id) (new_amount)', value='Update the payment amount for an order.', inline=False)
    embed.add_field(name='.payinfo (order_id)', value='See infos about payment.', inline=False)
    embed.add_field(name='.pdelete (order_id)', value='Delete payment.', inline=False)
    embed.add_field(name='.pverify (order_id)', value='verify payment. That is Suspicius', inline=False)
    embed.add_field(name='.phelp', value='Display this command list.', inline=False)

    await ctx.send(embed=embed)

@bot.command()
@commands.check(has_required_role)
async def pdelete(ctx, order_id):
    if order_id in payments:
        del payments[order_id]
        save_payments(payments)
        
        embed = discord.Embed(
            title=f'Order Deleted',
            description=f'Order with order ID {order_id} has been deleted.',
            color=0x00FF00  # Green
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title='Order Not Found',
            description='Order not found. Please provide a valid order ID.',
            color=0xFF0000  # red
        )
        await ctx.send(embed=embed)

@bot.command()
@commands.check(has_required_role)  
async def pverify(ctx, order_id: str):
    payment_channel = bot.get_channel(payment_channel_id)

    if order_id in [data['order_id'] for data in payments.values()]:
        for user_id, data in payments.items():
            if data['order_id'] == order_id:
                user = await bot.fetch_user(user_id)
                if data['status'] == 'Pending Verification':
                    data['status'] = 'Confirmed'  # set confirmed
                    save_payments(payments)

                    embed = discord.Embed(
                        title='Order Confirmed',
                        description=f'Your order with order number {order_id} has been confirmed and is now complete.',
                        color=0x00FF00  # Green
                    )
                    await user.send(embed=embed)
                    await payment_channel.send(f'**Order with order number {order_id} has been confirmed by {ctx.author.mention}.**')
                    await ctx.send(f'Order with order number {order_id} has been confirmed and is now complete.')
                    return

    await ctx.send('The specified order number was not found, is already completed, or has not been checked for verification.')



#----------------- END BOT CODE-------------------------

from colorama import Fore, Style, init
import os

init(autoreset=True)  


os.system('cls' if os.name == 'nt' else 'clear')


header = f"""
{Fore.MAGENTA}{Style.BRIGHT}  
{Fore.MAGENTA}{Style.BRIGHT}  /$$$$$$$                    
{Fore.MAGENTA}{Style.BRIGHT} | $$__  $$                   
{Fore.MAGENTA}{Style.BRIGHT} | $$  \ $$ /$$$$$$  /$$   /$$
{Fore.MAGENTA}{Style.BRIGHT} | $$$$$$$/|____  $$| $$  | $$
{Fore.MAGENTA}{Style.BRIGHT} | $$____/  /$$$$$$$| $$  | $$
{Fore.MAGENTA}{Style.BRIGHT} | $$      /$$__  $$| $$  | $$
{Fore.MAGENTA}{Style.BRIGHT} | $$     |  $$$$$$$|  $$$$$$$
{Fore.MAGENTA}{Style.BRIGHT} |__/      \_______/ \____  $$
{Fore.MAGENTA}{Style.BRIGHT}                     /$$  | $$
{Fore.MAGENTA}{Style.BRIGHT}                    |  $$$$$$/
{Fore.MAGENTA}{Style.BRIGHT}                     \______/ 
{Fore.MAGENTA}{Style.BRIGHT}  

{Style.RESET_ALL}
"""

print(header)

@bot.event
async def on_command(ctx):
    await ctx.message.add_reaction('👍')

bot.run('INSERT TOKEN HERE')
