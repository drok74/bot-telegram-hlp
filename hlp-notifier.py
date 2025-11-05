import requests
import os
import json
from datetime import datetime, timedelta, timezone
from hyperliquid.info import Info
from hyperliquid.utils import constants
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
import asyncio

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN environment variable is required. "
        "Please set it in your environment or Railway settings."
    )

HYPERLIQUID_API = "https://api.hyperliquid.xyz/info"
VAULTS_ANALYSER_API = "https://vaults-analyser.com/pub_api/v1"

# Token for vaults-analyser.com (optional)
VAULTS_ANALYSER_TOKEN = os.getenv("VAULTS_ANALYSER_TOKEN")

# File to store user addresses
USER_ADDRESSES_FILE = "user_addresses.json"

# Dictionary to store user addresses (user_id -> address)
user_addresses = {}

def load_user_addresses():
    """Load addresses from JSON file"""
    global user_addresses
    try:
        if os.path.exists(USER_ADDRESSES_FILE):
            with open(USER_ADDRESSES_FILE, 'r') as f:
                user_addresses = json.load(f)
    except Exception as e:
        print(f"Error loading addresses: {e}")
        user_addresses = {}

def save_user_addresses():
    """Save addresses to JSON file"""
    try:
        with open(USER_ADDRESSES_FILE, 'w') as f:
            json.dump(user_addresses, f, indent=2)
    except Exception as e:
        print(f"Error saving addresses: {e}")

def get_hlp_vault_performance():
    """Retrieves HLP vault data"""
    try:
        payload = {
            "type": "vaultDetails",
            "vaultAddress": "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"  # HLP vault address
        }
        response = requests.post(HYPERLIQUID_API, json=payload)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving vault data: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"Error retrieving vault data: {e}")
        return None

def get_all_vault_depositors(vault_address):
    """Retrieves the complete list of all vault depositors via vaults-analyser.com"""
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
            print("vaults-analyser authentication error: Invalid or expired token")
            return None
        elif response.status_code == 404:
            print("Vault not found on vaults-analyser")
            return None
        else:
            print(f"vaults-analyser API error: {response.status_code} - {response.text[:200]}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving depositors from vaults-analyser: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def get_user_vault_position(wallet_address, vault_data=None):
    """Retrieves your position in the HLP vault using Hyperliquid SDK"""
    vault_address = "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"
    
    # Use Hyperliquid SDK to get current value (most reliable method)
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
                            print(f"Conversion error: {e}")
                            return None
    except Exception as e:
        print(f"Hyperliquid SDK error: {e}")
    
    # If we have SDK value, retrieve initial deposit from vaults-analyser to calculate total PnL
    if equity_from_sdk is not None:
        initial_deposit = None
        all_time_pnl_calculated = None
        
        # Try vaults-analyser first to get initial deposit
        all_depositors = get_all_vault_depositors(vault_address)
        if all_depositors:
            print(f"DEBUG: Found {len(all_depositors)} depositors from vaults-analyser")
            for depositor in all_depositors:
                if isinstance(depositor, dict) and depositor.get('user', '').lower() == wallet_address.lower():
                    print(f"DEBUG: Found user in vaults-analyser: {depositor}")
                    vault_equity_va = depositor.get('vault_equity', None)
                    all_time_pnl_va = depositor.get('all_time_pnl', None)
                    print(f"DEBUG: vault_equity_va={vault_equity_va}, all_time_pnl_va={all_time_pnl_va}")
                    if vault_equity_va is not None and all_time_pnl_va is not None:
                        try:
                            vault_equity_va = float(vault_equity_va) if isinstance(vault_equity_va, str) else vault_equity_va
                            all_time_pnl_va = float(all_time_pnl_va) if isinstance(all_time_pnl_va, str) else all_time_pnl_va
                            initial_deposit = vault_equity_va - all_time_pnl_va
                            
                            total_pnl_calculated = equity_from_sdk - initial_deposit
                            
                            print(f"DEBUG: Calculated initial_deposit={initial_deposit}, total_pnl_calculated={total_pnl_calculated}")
                            
                            return {
                                'equity': equity_from_sdk,
                                'lockedUntil': locked_until,
                                'pnl': depositor.get('pnl', 0),
                                'allTimePnl': total_pnl_calculated,
                                'initialDeposit': initial_deposit
                            }
                        except (ValueError, TypeError) as e:
                            print(f"Initial deposit calculation error: {e}")
                    break
        else:
            print("DEBUG: No depositors found from vaults-analyser")
        
        # Try followers list (top 100) as fallback
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
        
        # If initial deposit not found, return with equity anyway
        return {
            'equity': equity_from_sdk,
            'lockedUntil': locked_until,
            'pnl': 0,
            'allTimePnl': None,
            'initialDeposit': None
        }
    
    # Fallback 1: Search in followers list (top 100)
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
    
    # Fallback 2: Try vaults-analyser (may not be up to date)
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
    """Extracts vault metrics from API data (rolling 24h)"""
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
        print(f"Error extracting metrics: {e}")
    
    return metrics

def extract_yesterday_vault_metrics(vault_data):
    """Extracts vault metrics for yesterday's calendar day (00:00 to 23:59)"""
    metrics = {
        'tvl': 0,
        'yesterday_pnl_percent': 0,
        'yesterday_pnl_amount': 0,
        'yesterday_start_value': 0,
        'yesterday_end_value': 0
    }
    
    try:
        # Get yesterday's date range (00:00 to 23:59:59) in UTC
        now = datetime.now(timezone.utc)
        yesterday_date = (now - timedelta(days=1)).date()
        
        yesterday_start = datetime.combine(
            yesterday_date,
            datetime.min.time(),
            timezone.utc
        )
        yesterday_end = datetime.combine(
            yesterday_date,
            datetime.max.time(),
            timezone.utc
        )
        
        # Convert to milliseconds (timestamp format used by API)
        yesterday_start_ms = int(yesterday_start.timestamp() * 1000)
        yesterday_end_ms = int(yesterday_end.timestamp() * 1000)
        
        portfolio = vault_data.get('portfolio', [])
        day_data = None
        alltime_data = None
        
        # Try to get data from 'day' period first, then 'allTime'
        for period_data in portfolio:
            if isinstance(period_data, list) and len(period_data) >= 2:
                period_name = period_data[0]
                period_info = period_data[1]
                
                if period_name == 'day' and isinstance(period_info, dict):
                    day_data = period_info
                elif period_name == 'allTime' and isinstance(period_info, dict):
                    alltime_data = period_info
        
        # Try to find yesterday's data in day_data first
        data_source = day_data if day_data else alltime_data
        
        if data_source:
            account_history = data_source.get('accountValueHistory', [])
            pnl_history = data_source.get('pnlHistory', [])
            
            # Filter data for yesterday only
            yesterday_account_history = []
            yesterday_pnl_history = []
            
            for entry in account_history:
                if isinstance(entry, list) and len(entry) >= 2:
                    timestamp = entry[0]
                    if yesterday_start_ms <= timestamp <= yesterday_end_ms:
                        yesterday_account_history.append(entry)
            
            for entry in pnl_history:
                if isinstance(entry, list) and len(entry) >= 2:
                    timestamp = entry[0]
                    if yesterday_start_ms <= timestamp <= yesterday_end_ms:
                        yesterday_pnl_history.append(entry)
            
            # Calculate using pnlHistory (preferred method)
            if yesterday_pnl_history and len(yesterday_pnl_history) >= 2:
                first_pnl = float(yesterday_pnl_history[0][1])
                last_pnl = float(yesterday_pnl_history[-1][1])
                metrics['yesterday_pnl_amount'] = last_pnl - first_pnl
                
                if yesterday_account_history and len(yesterday_account_history) >= 1:
                    first_value = float(yesterday_account_history[0][1])
                    metrics['yesterday_start_value'] = first_value
                    if first_value > 0:
                        metrics['yesterday_pnl_percent'] = (metrics['yesterday_pnl_amount'] / first_value) * 100
                    
                    # Get end value
                    if len(yesterday_account_history) >= 1:
                        metrics['yesterday_end_value'] = float(yesterday_account_history[-1][1])
                        metrics['tvl'] = metrics['yesterday_end_value']
            
            # Fallback: use accountValueHistory
            elif yesterday_account_history and len(yesterday_account_history) >= 2:
                first_entry = yesterday_account_history[0]
                last_entry = yesterday_account_history[-1]
                if (isinstance(first_entry, list) and len(first_entry) >= 2 and
                    isinstance(last_entry, list) and len(last_entry) >= 2):
                    first_value = float(first_entry[1])
                    last_value = float(last_entry[1])
                    metrics['yesterday_start_value'] = first_value
                    metrics['yesterday_end_value'] = last_value
                    metrics['tvl'] = last_value
                    metrics['yesterday_pnl_amount'] = last_value - first_value
                    
                    if first_value > 0:
                        metrics['yesterday_pnl_percent'] = ((last_value - first_value) / first_value) * 100
            
            # If no data found for yesterday in filtered data, try to get closest values
            elif account_history and len(account_history) >= 2:
                # Find entries closest to yesterday start and end
                closest_start_entry = None
                closest_end_entry = None
                min_start_diff = float('inf')
                min_end_diff = float('inf')
                
                for entry in account_history:
                    if isinstance(entry, list) and len(entry) >= 2:
                        timestamp = entry[0]
                        start_diff = abs(timestamp - yesterday_start_ms)
                        end_diff = abs(timestamp - yesterday_end_ms)
                        
                        if start_diff < min_start_diff:
                            min_start_diff = start_diff
                            closest_start_entry = entry
                        
                        if end_diff < min_end_diff:
                            min_end_diff = end_diff
                            closest_end_entry = entry
                
                # Use closest entries if within reasonable time range (within 6 hours)
                if closest_start_entry and closest_end_entry:
                    start_timestamp = closest_start_entry[0]
                    end_timestamp = closest_end_entry[0]
                    
                    # Check if entries are reasonably close to yesterday's boundaries
                    if (abs(start_timestamp - yesterday_start_ms) < 6 * 60 * 60 * 1000 and
                        abs(end_timestamp - yesterday_end_ms) < 6 * 60 * 60 * 1000):
                        
                        first_value = float(closest_start_entry[1])
                        last_value = float(closest_end_entry[1])
                        metrics['yesterday_start_value'] = first_value
                        metrics['yesterday_end_value'] = last_value
                        metrics['tvl'] = last_value
                        metrics['yesterday_pnl_amount'] = last_value - first_value
                        
                        if first_value > 0:
                            metrics['yesterday_pnl_percent'] = ((last_value - first_value) / first_value) * 100
        
    except Exception as e:
        print(f"Error extracting yesterday metrics: {e}")
        import traceback
        traceback.print_exc()
    
    return metrics

def format_performance_message(vault_data, user_data, user_pnl, user_pnl_percent, yesterday_metrics=None):
    """Formats the performance message"""
    today = datetime.now().strftime("%m/%d/%Y")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%m/%d/%Y")
    
    # Use yesterday metrics if available
    if yesterday_metrics and yesterday_metrics.get('yesterday_pnl_percent', 0) != 0:
        vault_pnl_percent = yesterday_metrics.get('yesterday_pnl_percent', 0)
        vault_tvl = yesterday_metrics.get('tvl', 0)
        period_label = f"Yesterday ({yesterday})"
    else:
        # Fallback to rolling 24h
        vault_metrics = extract_vault_metrics(vault_data)
        vault_pnl_percent = vault_metrics['daily_pnl_percent']
        vault_tvl = vault_metrics['tvl']
        period_label = "Last 24h (Rolling)"
    
    vault_emoji = "📈" if vault_pnl_percent > 0 else "📉"
    user_emoji = "✅" if user_pnl > 0 else "❌" if user_pnl < 0 else "➖"
    
    tvl_str = f"${vault_tvl:,.2f}" if vault_tvl > 0 else "N/A"
    
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
        
        # Debug logging
        print(f"DEBUG format_performance_message: user_equity={user_equity}, all_time_pnl={all_time_pnl}, initial_deposit={initial_deposit}")
        
        # Calculate Total PnL: same method as v1
        # Priority: use allTimePnl if available, otherwise calculate from current_value - initialDeposit
        if all_time_pnl is not None and initial_deposit is not None and initial_deposit > 0:
            try:
                all_time_pnl = float(all_time_pnl) if isinstance(all_time_pnl, str) else all_time_pnl
                initial_deposit = float(initial_deposit) if isinstance(initial_deposit, str) else initial_deposit
                
                all_time_pnl_percent = (all_time_pnl / initial_deposit) * 100
                total_pnl_emoji = "✅" if all_time_pnl > 0 else "❌" if all_time_pnl < 0 else "➖"
                total_pnl_str = f"{total_pnl_emoji} ${all_time_pnl:,.2f} ({all_time_pnl_percent:+.2f}%)"
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Error formatting total PnL with deposit: {e}")
                total_pnl_str = "N/A"
        elif all_time_pnl is not None:
            try:
                all_time_pnl = float(all_time_pnl) if isinstance(all_time_pnl, str) else all_time_pnl
                # Show Total PnL even if zero
                total_pnl_emoji = "✅" if all_time_pnl > 0 else "❌" if all_time_pnl < 0 else "➖"
                total_pnl_str = f"{total_pnl_emoji} ${all_time_pnl:,.2f}"
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Error formatting total PnL without deposit: {e}")
                total_pnl_str = "N/A"
        elif initial_deposit is not None and user_equity > 0:
            # Fallback: calculate Total PnL from current_value - initialDeposit (same as v1)
            try:
                initial_deposit = float(initial_deposit) if isinstance(initial_deposit, str) else initial_deposit
                calculated_total_pnl = user_equity - initial_deposit
                if initial_deposit > 0:
                    calculated_total_pnl_percent = (calculated_total_pnl / initial_deposit) * 100
                    total_pnl_emoji = "✅" if calculated_total_pnl > 0 else "❌" if calculated_total_pnl < 0 else "➖"
                    total_pnl_str = f"{total_pnl_emoji} ${calculated_total_pnl:,.2f} ({calculated_total_pnl_percent:+.2f}%)"
                else:
                    total_pnl_emoji = "✅" if calculated_total_pnl > 0 else "❌" if calculated_total_pnl < 0 else "➖"
                    total_pnl_str = f"{total_pnl_emoji} ${calculated_total_pnl:,.2f}"
                print(f"DEBUG: Calculated Total PnL from current_value - initialDeposit: {calculated_total_pnl}")
            except (ValueError, TypeError) as e:
                print(f"DEBUG: Error calculating total PnL from deposit: {e}")
                total_pnl_str = "N/A"
        else:
            print(f"DEBUG: all_time_pnl is None and cannot calculate from initialDeposit")
            total_pnl_str = "N/A"
    else:
        equity_str = "N/A"
        total_pnl_str = "N/A"
    
    pnl_label = "Yesterday PnL" if yesterday_metrics and yesterday_metrics.get('yesterday_pnl_percent', 0) != 0 else "24h PnL"
    
    message = f"""
<b>🏦 HLP Vault Performance - {today}</b>

<b>📊 Global Vault ({period_label}):</b>
• TVL: {tvl_str}
• Performance: {vault_emoji} {vault_pnl_percent:.2f}%

<b>💼 Your Position:</b>
• Current Value: {equity_str}
• {pnl_label}: {user_emoji} ${user_pnl:,.2f} ({user_pnl_percent:+.2f}%)
• Total PnL: {total_pnl_str}{("" if user_data else "\n\n⚠️ Position not found. Please verify that your address is correct and that you have funds in the HLP vault.")}
"""
    return message

async def generate_report(wallet_address):
    """Generates a report for a given address"""
    vault_data = get_hlp_vault_performance()
    
    if not vault_data:
        return "⚠️ Error retrieving vault data"
    
    user_data = get_user_vault_position(wallet_address, vault_data)
    
    # Get yesterday's metrics (calendar day)
    yesterday_metrics = extract_yesterday_vault_metrics(vault_data)
    
    # Calculate user's PnL for yesterday
    if user_data and isinstance(user_data, dict):
        current_value = user_data.get('equity', 0)
        if isinstance(current_value, str):
            try:
                current_value = float(current_value)
            except ValueError:
                current_value = 0
    else:
        current_value = 0
    
    # Calculate yesterday's PnL
    # Use yesterday's vault performance to estimate user's PnL
    if yesterday_metrics.get('yesterday_pnl_percent', 0) != 0:
        # Use yesterday's vault performance percentage
        user_yesterday_pnl_percent = yesterday_metrics['yesterday_pnl_percent']
        
        # Calculate user's PnL for yesterday
        # To be accurate, we need to estimate the user's position value at the END of yesterday
        # Then apply yesterday's performance to get the PnL
        
        vault_yesterday_end = yesterday_metrics.get('yesterday_end_value', 0)
        
        # Get current vault TVL
        vault_metrics_current = extract_vault_metrics(vault_data)
        vault_current = vault_metrics_current.get('tvl', 0)
        
        if current_value > 0 and vault_yesterday_end > 0 and vault_current > 0:
            # Estimate user's position value at end of yesterday
            # By scaling proportionally: user_end_yesterday / user_current = vault_end_yesterday / vault_current
            # So: user_end_yesterday = user_current * (vault_end_yesterday / vault_current)
            estimated_user_end_yesterday = current_value * (vault_yesterday_end / vault_current)
            
            # Calculate PnL: if performance was X%, then:
            # value_end = value_start * (1 + X%)
            # So: value_start = value_end / (1 + X%)
            # PnL = value_end - value_start = value_end - value_end/(1+X%) = value_end * (X% / (1+X%))
            
            if user_yesterday_pnl_percent != -100:  # Avoid division by zero
                estimated_user_start_yesterday = estimated_user_end_yesterday / (1 + user_yesterday_pnl_percent / 100)
                user_yesterday_pnl = estimated_user_end_yesterday - estimated_user_start_yesterday
            else:
                # If -100%, everything was lost
                user_yesterday_pnl = -estimated_user_end_yesterday
        elif current_value > 0:
            # Fallback: use simple proportional method (same as v1 but with yesterday's %)
            user_yesterday_pnl = current_value * (user_yesterday_pnl_percent / 100)
        else:
            user_yesterday_pnl = 0
    else:
        # Fallback: use rolling 24h metrics if yesterday data not available
        vault_metrics = extract_vault_metrics(vault_data)
        user_yesterday_pnl = current_value * (vault_metrics['daily_pnl_percent'] / 100) if current_value > 0 else 0
        user_yesterday_pnl_percent = vault_metrics['daily_pnl_percent']
        yesterday_metrics = None  # Mark as unavailable
    
    message = format_performance_message(
        vault_data, 
        user_data, 
        user_yesterday_pnl, 
        user_yesterday_pnl_percent,
        yesterday_metrics=yesterday_metrics
    )
    return message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command"""
    keyboard = [
        [InlineKeyboardButton("📝 Set My Address", callback_data='set_address')],
        [InlineKeyboardButton("📊 Get Report", callback_data='get_report')],
        [InlineKeyboardButton("ℹ️ View My Address", callback_data='view_address')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_id = str(update.effective_user.id)
    current_address = user_addresses.get(user_id, None)
    
    welcome_text = "👋 <b>Welcome to the HLP Performance Tracker Bot!</b>\n\n"
    welcome_text += "This bot allows you to track your performance in the Hyperliquid HLP vault.\n\n"
    welcome_text += "<b>🆕 NEW:</b> Reports now show yesterday's performance (calendar day)!\n\n"
    
    if current_address:
        welcome_text += f"📍 <b>Registered Address:</b> <code>{current_address[:10]}...{current_address[-8:]}</code>\n\n"
    else:
        welcome_text += "⚠️ <b>No address registered.</b> Please set your address to get started.\n\n"
    
    welcome_text += "Use the menu below to navigate:"
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles clicks on menu buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    
    if query.data == 'set_address':
        await query.edit_message_text(
            "📝 <b>Set Address</b>\n\n"
            "Please send your Hyperliquid wallet address.\n\n"
            "Expected format: <code>0x...</code>",
            parse_mode='HTML'
        )
        context.user_data['waiting_for_address'] = True
    
    elif query.data == 'get_report':
        current_address = user_addresses.get(user_id, None)
        
        if not current_address:
            keyboard = [
                [InlineKeyboardButton("📝 Set My Address", callback_data='set_address')],
                [InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "⚠️ <b>No address registered</b>\n\n"
                "Please set your wallet address first to get your report.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return
        
        await query.edit_message_text("⏳ <b>Retrieving data...</b>", parse_mode='HTML')
        
        report = await generate_report(current_address)
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data='get_report')],
            [InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]
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
            [InlineKeyboardButton("✏️ Edit Address", callback_data='set_address')],
            [InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if current_address:
            await query.edit_message_text(
                f"📍 <b>Your Registered Address:</b>\n\n"
                f"<code>{current_address}</code>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                "⚠️ <b>No address registered</b>\n\n"
                "Please set your address to get started.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    
    elif query.data == 'back_to_menu':
        keyboard = [
            [InlineKeyboardButton("📝 Set My Address", callback_data='set_address')],
            [InlineKeyboardButton("📊 Get Report", callback_data='get_report')],
            [InlineKeyboardButton("ℹ️ View My Address", callback_data='view_address')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_address = user_addresses.get(user_id, None)
        
        welcome_text = "👋 <b>Main Menu</b>\n\n"
        
        if current_address:
            welcome_text += f"📍 <b>Registered Address:</b> <code>{current_address[:10]}...{current_address[-8:]}</code>\n\n"
        else:
            welcome_text += "⚠️ <b>No address registered.</b> Please set your address to get started.\n\n"
        
        welcome_text += "Use the menu below to navigate:"
        
        await query.edit_message_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages (for address input)"""
    if context.user_data.get('waiting_for_address', False):
        user_id = str(update.effective_user.id)
        address = update.message.text.strip()
        
        # Basic address validation
        if not address.startswith('0x') or len(address) != 42:
            await update.message.reply_text(
                "❌ <b>Invalid address format</b>\n\n"
                "Please send a valid Ethereum address (starts with 0x and is 42 characters long).\n\n"
                "Example: <code>0xec0cf15a2857d39f9ff55bc532a977fa590e5161</code>",
                parse_mode='HTML'
            )
            return
        
        # Save address
        user_addresses[user_id] = address
        save_user_addresses()
        
        context.user_data['waiting_for_address'] = False
        
        keyboard = [
            [InlineKeyboardButton("📊 Get Report", callback_data='get_report')],
            [InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ <b>Address registered successfully!</b>\n\n"
            f"Address: <code>{address}</code>\n\n"
            "You can now get your performance report.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        # If user sends a message without context, show menu
        keyboard = [
            [InlineKeyboardButton("📝 Set My Address", callback_data='set_address')],
            [InlineKeyboardButton("📊 Get Report", callback_data='get_report')],
            [InlineKeyboardButton("ℹ️ View My Address", callback_data='view_address')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👋 Use the menu below to navigate:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command"""
    help_text = """
<b>📖 Help - HLP Performance Tracker Bot</b>

<b>Available Commands:</b>
/start - Show main menu
/help - Show this help
/report - Get your performance report (requires a registered address)

<b>Features:</b>
• Track your performance in the Hyperliquid HLP vault
• View your daily and total PnL
• Visualize global vault metrics
• <b>NEW:</b> Reports show yesterday's calendar day performance

<b>How to use:</b>
1. Set your wallet address via the menu
2. Use "Get Report" to see your performance
3. Refresh the report at any time

<b>Note:</b> If your position doesn't appear, please verify that your address is correct and that you have funds in the HLP vault.
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /report command"""
    user_id = str(update.effective_user.id)
    current_address = user_addresses.get(user_id, None)
    
    if not current_address:
        keyboard = [
            [InlineKeyboardButton("📝 Set My Address", callback_data='set_address')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ <b>No address registered</b>\n\n"
            "Please set your wallet address first to get your report.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return
    
    message = await update.message.reply_text("⏳ <b>Retrieving data...</b>", parse_mode='HTML')
    
    report = await generate_report(current_address)
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data='get_report')],
        [InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.edit_text(
        report,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

def main():
    """Main function"""
    print("HLP Performance Tracker Bot v2 started")
    print("NEW: Calculates yesterday's calendar day performance")
    
    # Load saved addresses
    load_user_addresses()
    print(f"Loaded addresses: {len(user_addresses)} user(s)")
    
    # Create Telegram application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start bot
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

