import requests
import os
import json
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
import asyncio

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8484118476:AAH8lQzlhViyT8mEg5eWp7iaZtbDA8woSS0")
HYPERLIQUID_API = "https://api.hyperliquid.xyz/info"
VAULTS_ANALYSER_API = "https://vaults-analyser.com/pub_api/v1"

# Token pour vaults-analyser.com (optionnel)
VAULTS_ANALYSER_TOKEN = os.getenv("VAULTS_ANALYSER_TOKEN", "vjtEN0sSsCOs7XCmK0YNH6912x9YrOlLkkiSV6oD0c58677f")

# Fichier pour stocker les adresses des utilisateurs
USER_ADDRESSES_FILE = "user_addresses.json"

# Dictionnaire pour stocker les adresses des utilisateurs (user_id -> address)
user_addresses = {}

def load_user_addresses():
    """Charge les adresses depuis le fichier JSON"""
    global user_addresses
    try:
        if os.path.exists(USER_ADDRESSES_FILE):
            with open(USER_ADDRESSES_FILE, 'r') as f:
                user_addresses = json.load(f)
    except Exception as e:
        print(f"Erreur lors du chargement des adresses: {e}")
        user_addresses = {}

def save_user_addresses():
    """Sauvegarde les adresses dans le fichier JSON"""
    try:
        with open(USER_ADDRESSES_FILE, 'w') as f:
            json.dump(user_addresses, f, indent=2)
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des adresses: {e}")

def get_hlp_vault_performance():
    """Récupère les données du vault HLP"""
    try:
        payload = {
            "type": "vaultDetails",
            "vaultAddress": "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"  # Adresse du vault HLP
        }
        response = requests.post(HYPERLIQUID_API, json=payload)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des données du vault: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"Erreur lors de la récupération des données du vault: {e}")
        return None

def get_all_vault_depositors(vault_address):
    """Récupère la liste complète de tous les déposants du vault via vaults-analyser.com"""
    if not VAULTS_ANALYSER_TOKEN:
        return None
    
    try:
        url = f"{VAULTS_ANALYSER_API}/depositors/{vault_address}"
        headers = {
            "Authorization": f"Bearer {VAULTS_ANALYSER_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            elif isinstance(data, list):
                return data
            return []
        elif response.status_code == 401:
            print("Erreur d'authentification vaults-analyser: Token invalide ou expiré")
            return None
        elif response.status_code == 404:
            print("Vault non trouvé sur vaults-analyser")
            return None
        else:
            print(f"Erreur vaults-analyser API: {response.status_code} - {response.text[:200]}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des déposants depuis vaults-analyser: {e}")
        return None
    except Exception as e:
        print(f"Erreur inattendue: {e}")
        return None

def get_user_vault_position(wallet_address, vault_data=None):
    """Récupère votre position dans le vault HLP en utilisant le SDK Hyperliquid"""
    vault_address = "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"
    
    # Utiliser le SDK Hyperliquid pour obtenir la valeur actuelle (méthode la plus fiable)
    equity_from_sdk = None
    locked_until = 0
    try:
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        vault_equities = info.user_vault_equities(wallet_address)
        
        if isinstance(vault_equities, list):
            for vault_info in vault_equities:
                if isinstance(vault_info, dict):
                    vault_addr = vault_info.get('vaultAddress', '')
                    if vault_addr.lower() == vault_address.lower():
                        equity = vault_info.get('equity', '0')
                        try:
                            equity_from_sdk = float(equity) if isinstance(equity, str) else equity
                            locked_until = vault_info.get('lockedUntilTimestamp', 0)
                            break
                        except (ValueError, TypeError) as e:
                            print(f"Erreur de conversion: {e}")
                            return None
    except Exception as e:
        print(f"Erreur SDK Hyperliquid: {e}")
    
    # Si on a la valeur du SDK, récupérer le dépôt initial depuis vaults-analyser pour calculer le PnL total
    if equity_from_sdk is not None:
        initial_deposit = None
        
        # Essayer d'abord vaults-analyser pour obtenir le dépôt initial
        all_depositors = get_all_vault_depositors(vault_address)
        if all_depositors:
            for depositor in all_depositors:
                if isinstance(depositor, dict) and depositor.get('user', '').lower() == wallet_address.lower():
                    vault_equity_va = depositor.get('vault_equity', None)
                    all_time_pnl_va = depositor.get('all_time_pnl', None)
                    if vault_equity_va is not None and all_time_pnl_va is not None:
                        try:
                            vault_equity_va = float(vault_equity_va) if isinstance(vault_equity_va, str) else vault_equity_va
                            all_time_pnl_va = float(all_time_pnl_va) if isinstance(all_time_pnl_va, str) else all_time_pnl_va
                            initial_deposit = vault_equity_va - all_time_pnl_va
                            
                            total_pnl_calculated = equity_from_sdk - initial_deposit
                            
                            return {
                                'equity': equity_from_sdk,
                                'lockedUntil': locked_until,
                                'pnl': depositor.get('pnl', 0),
                                'allTimePnl': total_pnl_calculated,
                                'initialDeposit': initial_deposit
                            }
                        except (ValueError, TypeError) as e:
                            print(f"Erreur de calcul du dépôt initial: {e}")
                    break
        
        # Essayer dans followers list (top 100) comme fallback
        if initial_deposit is None and vault_data and isinstance(vault_data, dict):
            followers = vault_data.get('followers', [])
            if isinstance(followers, list):
                for follower in followers:
                    if isinstance(follower, dict) and follower.get('user', '').lower() == wallet_address.lower():
                        vault_equity_f = follower.get('vaultEquity', None)
                        all_time_pnl_f = follower.get('allTimePnl', None)
                        if vault_equity_f is not None and all_time_pnl_f is not None:
                            try:
                                vault_equity_f = float(vault_equity_f) if isinstance(vault_equity_f, str) else vault_equity_f
                                all_time_pnl_f = float(all_time_pnl_f) if isinstance(all_time_pnl_f, str) else all_time_pnl_f
                                initial_deposit = vault_equity_f - all_time_pnl_f
                                total_pnl_calculated = equity_from_sdk - initial_deposit
                                
                                return {
                                    'equity': equity_from_sdk,
                                    'lockedUntil': locked_until,
                                    'pnl': follower.get('pnl', 0),
                                    'allTimePnl': total_pnl_calculated,
                                    'initialDeposit': initial_deposit
                                }
                            except (ValueError, TypeError):
                                pass
                        break
        
        # Si on n'a pas trouvé le dépôt initial, retourner quand même avec equity
        return {
            'equity': equity_from_sdk,
            'lockedUntil': locked_until,
            'pnl': 0,
            'allTimePnl': None,
            'initialDeposit': None
        }
    
    # Fallback 1: Chercher dans followers list (top 100)
    if vault_data and isinstance(vault_data, dict):
        followers = vault_data.get('followers', [])
        if isinstance(followers, list):
            for follower in followers:
                if isinstance(follower, dict) and follower.get('user', '').lower() == wallet_address.lower():
                    equity = follower.get('vaultEquity', '0')
                    try:
                        equity_float = float(equity) if isinstance(equity, str) else equity
                        return {
                            'equity': equity_float,
                            'pnl': follower.get('pnl', 0),
                            'allTimePnl': follower.get('allTimePnl', 0)
                        }
                    except (ValueError, TypeError):
                        return {'equity': 0, 'pnl': 0, 'allTimePnl': 0}
    
    # Fallback 2: Essayer vaults-analyser (peut ne pas être à jour)
    all_depositors = get_all_vault_depositors(vault_address)
    if all_depositors:
        for depositor in all_depositors:
            if isinstance(depositor, dict) and depositor.get('user', '').lower() == wallet_address.lower():
                vault_equity = depositor.get('vault_equity', 0)
                try:
                    equity_float = float(vault_equity) if isinstance(vault_equity, str) else vault_equity
                    return {
                        'equity': equity_float,
                        'pnl': depositor.get('pnl', 0),
                        'allTimePnl': depositor.get('all_time_pnl', 0)
                    }
                except (ValueError, TypeError):
                    pass
    
    return None

def extract_vault_metrics(vault_data):
    """Extrait les métriques du vault depuis les données de l'API"""
    metrics = {
        'tvl': 0,
        'daily_pnl_percent': 0,
        'apr': 0
    }
    
    try:
        portfolio = vault_data.get('portfolio', [])
        day_data = None
        alltime_data = None
        
        for period_data in portfolio:
            if isinstance(period_data, list) and len(period_data) >= 2:
                period_name = period_data[0]
                period_info = period_data[1]
                
                if period_name == 'day' and isinstance(period_info, dict):
                    day_data = period_info
                elif period_name == 'allTime' and isinstance(period_info, dict):
                    alltime_data = period_info
        
        if day_data:
            account_history = day_data.get('accountValueHistory', [])
            pnl_history = day_data.get('pnlHistory', [])
            
            if account_history and len(account_history) >= 1:
                latest_entry = account_history[-1]
                if isinstance(latest_entry, list) and len(latest_entry) >= 2:
                    metrics['tvl'] = float(latest_entry[1])
            
            if pnl_history and len(pnl_history) >= 2:
                first_pnl = float(pnl_history[0][1])
                last_pnl = float(pnl_history[-1][1])
                daily_pnl_amount = last_pnl - first_pnl
                
                if account_history and len(account_history) >= 1:
                    first_value = float(account_history[0][1])
                    if first_value > 0:
                        metrics['daily_pnl_percent'] = (daily_pnl_amount / first_value) * 100
            elif account_history and len(account_history) >= 2:
                first_entry = account_history[0]
                last_entry = account_history[-1]
                if (isinstance(first_entry, list) and len(first_entry) >= 2 and
                    isinstance(last_entry, list) and len(last_entry) >= 2):
                    first_value = float(first_entry[1])
                    last_value = float(last_entry[1])
                    if first_value > 0:
                        metrics['daily_pnl_percent'] = ((last_value - first_value) / first_value) * 100
        
        if alltime_data:
            account_history = alltime_data.get('accountValueHistory', [])
            pnl_history = alltime_data.get('pnlHistory', [])
            
            if pnl_history and len(pnl_history) >= 2:
                first_pnl_entry = pnl_history[0]
                last_pnl_entry = pnl_history[-1]
                if (isinstance(first_pnl_entry, list) and len(first_pnl_entry) >= 2 and
                    isinstance(last_pnl_entry, list) and len(last_pnl_entry) >= 2):
                    first_pnl = float(first_pnl_entry[1])
                    last_pnl = float(last_pnl_entry[1])
                    first_time = first_pnl_entry[0]
                    last_time = last_pnl_entry[0]
                    
                    total_pnl = last_pnl - first_pnl
                    time_diff_days = (last_time - first_time) / (1000 * 60 * 60 * 24)
                    
                    if account_history and len(account_history) >= 1:
                        current_tvl_entry = account_history[-1]
                        if isinstance(current_tvl_entry, list) and len(current_tvl_entry) >= 2:
                            current_tvl = float(current_tvl_entry[1])
                            
                            if time_diff_days > 0 and current_tvl > 0 and total_pnl != 0:
                                estimated_initial_tvl = current_tvl - total_pnl
                                if estimated_initial_tvl > 0:
                                    total_return_percent = (total_pnl / estimated_initial_tvl) * 100
                                    metrics['apr'] = (total_return_percent / time_diff_days) * 365
            
            elif account_history and len(account_history) >= 2:
                first_entry = account_history[0]
                last_entry = account_history[-1]
                if (isinstance(first_entry, list) and len(first_entry) >= 2 and
                    isinstance(last_entry, list) and len(last_entry) >= 2):
                    first_value = float(first_entry[1])
                    last_value = float(last_entry[1])
                    first_time = first_entry[0]
                    last_time = last_entry[0]
                    
                    time_diff_days = (last_time - first_time) / (1000 * 60 * 60 * 24)
                    
                    if time_diff_days > 0 and first_value > 0:
                        total_return_percent = ((last_value - first_value) / first_value) * 100
                        metrics['apr'] = (total_return_percent / time_diff_days) * 365
        
    except Exception as e:
        print(f"Erreur lors de l'extraction des métriques: {e}")
    
    return metrics

def format_performance_message(vault_data, user_data, user_pnl, user_pnl_percent):
    """Formate le message de performance"""
    today = datetime.now().strftime("%d/%m/%Y")
    
    vault_metrics = extract_vault_metrics(vault_data)
    
    vault_emoji = "📈" if vault_metrics['daily_pnl_percent'] > 0 else "📉"
    user_emoji = "✅" if user_pnl > 0 else "❌" if user_pnl < 0 else "➖"
    
    tvl_str = f"${vault_metrics['tvl']:,.2f}" if vault_metrics['tvl'] > 0 else "N/A"
    
    if user_data and isinstance(user_data, dict):
        user_equity = user_data.get('equity', 0)
        if isinstance(user_equity, str):
            try:
                user_equity = float(user_equity)
            except ValueError:
                user_equity = 0
        equity_str = f"${user_equity:,.2f}" if isinstance(user_equity, (int, float)) and user_equity > 0 else "N/A"
        
        all_time_pnl = user_data.get('allTimePnl', None)
        initial_deposit = user_data.get('initialDeposit', None)
        
        if all_time_pnl is not None and initial_deposit is not None and initial_deposit > 0:
            try:
                all_time_pnl = float(all_time_pnl) if isinstance(all_time_pnl, str) else all_time_pnl
                initial_deposit = float(initial_deposit) if isinstance(initial_deposit, str) else initial_deposit
                
                all_time_pnl_percent = (all_time_pnl / initial_deposit) * 100
                total_pnl_emoji = "✅" if all_time_pnl > 0 else "❌" if all_time_pnl < 0 else "➖"
                total_pnl_str = f"{total_pnl_emoji} ${all_time_pnl:,.2f} ({all_time_pnl_percent:+.2f}%)"
            except (ValueError, TypeError):
                total_pnl_str = "N/A"
        elif all_time_pnl is not None:
            try:
                all_time_pnl = float(all_time_pnl) if isinstance(all_time_pnl, str) else all_time_pnl
                total_pnl_emoji = "✅" if all_time_pnl > 0 else "❌" if all_time_pnl < 0 else "➖"
                total_pnl_str = f"{total_pnl_emoji} ${all_time_pnl:,.2f}"
            except (ValueError, TypeError):
                total_pnl_str = "N/A"
        else:
            total_pnl_str = "N/A"
    else:
        equity_str = "N/A"
        total_pnl_str = "N/A"
    
    message = f"""
<b>🏦 Performance HLP Vault - {today}</b>

<b>📊 Vault Global:</b>
• TVL: {tvl_str}
• Performance 24h: {vault_emoji} {vault_metrics['daily_pnl_percent']:.2f}%

<b>💼 Votre Position:</b>
• Valeur: {equity_str}
• PnL 24h: {user_emoji} ${user_pnl:,.2f} ({user_pnl_percent:+.2f}%)
• PnL Total: {total_pnl_str}{("" if user_data else "\n\n⚠️ Position non trouvée. Vérifiez que votre adresse est correcte et que vous avez des fonds dans le vault HLP.")}
"""
    return message

async def generate_report(wallet_address):
    """Génère un rapport pour une adresse donnée"""
    vault_data = get_hlp_vault_performance()
    
    if not vault_data:
        return "⚠️ Erreur lors de la récupération des données du vault"
    
    user_data = get_user_vault_position(wallet_address, vault_data)
    vault_metrics = extract_vault_metrics(vault_data)
    
    if user_data and isinstance(user_data, dict):
        current_value = user_data.get('equity', 0)
        if isinstance(current_value, str):
            try:
                current_value = float(current_value)
            except ValueError:
                current_value = 0
    else:
        current_value = 0
    
    user_pnl = current_value * (vault_metrics['daily_pnl_percent'] / 100) if current_value > 0 else 0
    user_pnl_percent = vault_metrics['daily_pnl_percent']
    
    message = format_performance_message(vault_data, user_data, user_pnl, user_pnl_percent)
    return message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /start"""
    keyboard = [
        [InlineKeyboardButton("📝 Définir mon adresse", callback_data='set_address')],
        [InlineKeyboardButton("📊 Obtenir le rapport", callback_data='get_report')],
        [InlineKeyboardButton("ℹ️ Voir mon adresse", callback_data='view_address')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_id = str(update.effective_user.id)
    current_address = user_addresses.get(user_id, None)
    
    welcome_text = "👋 <b>Bienvenue sur le Bot HLP Performance Tracker!</b>\n\n"
    welcome_text += "Ce bot vous permet de suivre votre performance dans le vault HLP d'Hyperliquid.\n\n"
    
    if current_address:
        welcome_text += f"📍 <b>Adresse enregistrée:</b> <code>{current_address[:10]}...{current_address[-8:]}</code>\n\n"
    else:
        welcome_text += "⚠️ <b>Aucune adresse enregistrée.</b> Veuillez définir votre adresse pour commencer.\n\n"
    
    welcome_text += "Utilisez le menu ci-dessous pour naviguer:"
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les clics sur les boutons du menu"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    
    if query.data == 'set_address':
        await query.edit_message_text(
            "📝 <b>Définition de l'adresse</b>\n\n"
            "Veuillez envoyer votre adresse wallet Hyperliquid.\n\n"
            "Format attendu: <code>0x...</code>",
            parse_mode='HTML'
        )
        context.user_data['waiting_for_address'] = True
    
    elif query.data == 'get_report':
        current_address = user_addresses.get(user_id, None)
        
        if not current_address:
            keyboard = [
                [InlineKeyboardButton("📝 Définir mon adresse", callback_data='set_address')],
                [InlineKeyboardButton("◀️ Retour au menu", callback_data='back_to_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "⚠️ <b>Aucune adresse enregistrée</b>\n\n"
                "Veuillez d'abord définir votre adresse wallet pour obtenir votre rapport.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return
        
        await query.edit_message_text("⏳ <b>Récupération des données...</b>", parse_mode='HTML')
        
        report = await generate_report(current_address)
        
        keyboard = [
            [InlineKeyboardButton("🔄 Actualiser", callback_data='get_report')],
            [InlineKeyboardButton("◀️ Retour au menu", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data == 'view_address':
        current_address = user_addresses.get(user_id, None)
        
        keyboard = [
            [InlineKeyboardButton("✏️ Modifier l'adresse", callback_data='set_address')],
            [InlineKeyboardButton("◀️ Retour au menu", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if current_address:
            await query.edit_message_text(
                f"📍 <b>Votre adresse enregistrée:</b>\n\n"
                f"<code>{current_address}</code>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                "⚠️ <b>Aucune adresse enregistrée</b>\n\n"
                "Veuillez définir votre adresse pour commencer.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    
    elif query.data == 'back_to_menu':
        keyboard = [
            [InlineKeyboardButton("📝 Définir mon adresse", callback_data='set_address')],
            [InlineKeyboardButton("📊 Obtenir le rapport", callback_data='get_report')],
            [InlineKeyboardButton("ℹ️ Voir mon adresse", callback_data='view_address')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_address = user_addresses.get(user_id, None)
        
        welcome_text = "👋 <b>Menu Principal</b>\n\n"
        
        if current_address:
            welcome_text += f"📍 <b>Adresse enregistrée:</b> <code>{current_address[:10]}...{current_address[-8:]}</code>\n\n"
        else:
            welcome_text += "⚠️ <b>Aucune adresse enregistrée.</b> Veuillez définir votre adresse pour commencer.\n\n"
        
        welcome_text += "Utilisez le menu ci-dessous pour naviguer:"
        
        await query.edit_message_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages texte (pour la saisie de l'adresse)"""
    if context.user_data.get('waiting_for_address', False):
        user_id = str(update.effective_user.id)
        address = update.message.text.strip()
        
        # Validation basique de l'adresse
        if not address.startswith('0x') or len(address) != 42:
            await update.message.reply_text(
                "❌ <b>Format d'adresse invalide</b>\n\n"
                "Veuillez envoyer une adresse Ethereum valide (commence par 0x et fait 42 caractères).\n\n"
                "Exemple: <code>0xec0cf15a2857d39f9ff55bc532a977fa590e5161</code>",
                parse_mode='HTML'
            )
            return
        
        # Sauvegarder l'adresse
        user_addresses[user_id] = address
        save_user_addresses()
        
        context.user_data['waiting_for_address'] = False
        
        keyboard = [
            [InlineKeyboardButton("📊 Obtenir le rapport", callback_data='get_report')],
            [InlineKeyboardButton("◀️ Retour au menu", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ <b>Adresse enregistrée avec succès!</b>\n\n"
            f"Adresse: <code>{address}</code>\n\n"
            "Vous pouvez maintenant obtenir votre rapport de performance.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        # Si l'utilisateur envoie un message sans contexte, afficher le menu
        keyboard = [
            [InlineKeyboardButton("📝 Définir mon adresse", callback_data='set_address')],
            [InlineKeyboardButton("📊 Obtenir le rapport", callback_data='get_report')],
            [InlineKeyboardButton("ℹ️ Voir mon adresse", callback_data='view_address')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👋 Utilisez le menu ci-dessous pour naviguer:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /help"""
    help_text = """
<b>📖 Aide - Bot HLP Performance Tracker</b>

<b>Commandes disponibles:</b>
/start - Afficher le menu principal
/help - Afficher cette aide
/report - Obtenir votre rapport de performance (nécessite une adresse enregistrée)

<b>Fonctionnalités:</b>
• Suivez votre performance dans le vault HLP d'Hyperliquid
• Consultez votre PnL quotidien et total
• Visualisez les métriques du vault global

<b>Comment utiliser:</b>
1. Définissez votre adresse wallet via le menu
2. Utilisez "Obtenir le rapport" pour voir vos performances
3. Actualisez le rapport à tout moment

<b>Note:</b> Si votre position n'apparaît pas, vérifiez que votre adresse est correcte et que vous avez des fonds dans le vault HLP.
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /report"""
    user_id = str(update.effective_user.id)
    current_address = user_addresses.get(user_id, None)
    
    if not current_address:
        keyboard = [
            [InlineKeyboardButton("📝 Définir mon adresse", callback_data='set_address')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ <b>Aucune adresse enregistrée</b>\n\n"
            "Veuillez d'abord définir votre adresse wallet pour obtenir votre rapport.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return
    
    message = await update.message.reply_text("⏳ <b>Récupération des données...</b>", parse_mode='HTML')
    
    report = await generate_report(current_address)
    
    keyboard = [
        [InlineKeyboardButton("🔄 Actualiser", callback_data='get_report')],
        [InlineKeyboardButton("◀️ Retour au menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.edit_text(
        report,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

def main():
    """Fonction principale"""
    print("Bot HLP Performance Tracker démarré")
    
    # Charger les adresses sauvegardées
    load_user_addresses()
    print(f"Adresses chargées: {len(user_addresses)} utilisateur(s)")
    
    # Créer l'application Telegram
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Ajouter les handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Démarrer le bot
    print("Bot en cours d'exécution...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

