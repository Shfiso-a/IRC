import socket
import threading
import json
import time
import sys
import argparse
import re
import os

# ANSI color codes for terminal coloring
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"

class IRCClient:
    def __init__(self, host='127.0.0.1', port=6969):
        """Initialize the IRC Client"""
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.connected = False
        self.current_channel = "#general"  # Default channel
        self.channels = set()
        self.channels.add(self.current_channel)
        
        # Message history for each channel
        self.message_history = {"#general": []}
        
        # Create a lock for thread-safe operations
        self.lock = threading.Lock()
        
    def connect(self, username):
        """Connect to the IRC server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.username = username
            
            # Send username to server
            self.socket.send(username.encode('utf-8'))
            
            # Start receiving messages in a separate thread
            self.connected = True
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            return True
        except Exception as e:
            print(f"{Colors.RED}Error connecting to server: {str(e)}{Colors.RESET}")
            return False
    
    def disconnect(self):
        """Disconnect from the IRC server"""
        if self.connected:
            try:
                self.send_command("QUIT", "", "Disconnecting")
                self.connected = False
                self.socket.close()
            except:
                pass
    
    def send_message(self, message):
        """Send a message to the current channel"""
        if not self.connected:
            print(f"{Colors.RED}Not connected to server.{Colors.RESET}")
            return False
        
        try:
            self.socket.send(message.encode('utf-8'))
            return True
        except Exception as e:
            print(f"{Colors.RED}Error sending message: {str(e)}{Colors.RESET}")
            self.connected = False
            return False
    
    def send_command(self, command, target="", content=""):
        """Send a command to the server"""
        cmd_str = f"/{command.lower()}"
        if target:
            cmd_str += f" {target}"
        if content:
            cmd_str += f" {content}"
        
        return self.send_message(cmd_str)
    
    def process_message(self, message_data):
        """Process incoming message"""
        try:
            # Try to parse as JSON (protocol message)
            message = json.loads(message_data)
            
            sender = message.get("sender", "")
            msg_type = message.get("type", "")
            recipient = message.get("recipient", "")
            content = message.get("content", "")
            
            # Format based on message type
            if msg_type == "system":
                # System message
                if recipient == "all" or recipient == self.username or recipient in self.channels:
                    self.display_message(f"{Colors.YELLOW}[SERVER] {content}{Colors.RESET}", recipient)
            
            elif msg_type == "channel":
                # Channel message
                if recipient in self.channels:
                    if sender == self.username:
                        # Own message
                        self.display_message(f"{Colors.GREEN}[{recipient}] {sender}: {content}{Colors.RESET}", recipient)
                    else:
                        # Others' message
                        self.display_message(f"{Colors.CYAN}[{recipient}] {sender}: {content}{Colors.RESET}", recipient)
            
            elif msg_type == "private":
                # Private message
                if recipient == self.username:
                    # Received PM
                    self.display_message(f"{Colors.MAGENTA}[PM from {sender}] {content}{Colors.RESET}", sender)
                elif sender == self.username:
                    # Sent PM
                    self.display_message(f"{Colors.MAGENTA}[PM to {recipient}] {content}{Colors.RESET}", recipient)
            
            return True
            
        except json.JSONDecodeError:
            # Not a JSON message, display as plain text
            self.display_message(f"{Colors.WHITE}{message_data}{Colors.RESET}", self.current_channel)
            return True
        
        except Exception as e:
            print(f"{Colors.RED}Error processing message: {str(e)}{Colors.RESET}")
            return False
    
    def display_message(self, formatted_message, channel):
        """Display a message and store in history"""
        with self.lock:
            # Store in channel history
            if channel not in self.message_history:
                self.message_history[channel] = []
            
            self.message_history[channel].append(formatted_message)
            
            # Only display if it's for the current channel or a PM
            if channel == self.current_channel or channel == self.username or channel == "SERVER":
                print(formatted_message)
    
    def switch_channel(self, channel):
        """Switch to a different channel"""
        if channel in self.channels:
            self.current_channel = channel
            
            # Display channel header
            print(f"\n{Colors.BOLD}{Colors.BLUE}===== Channel: {channel} ====={Colors.RESET}")
            
            # Show last few messages from channel history
            with self.lock:
                if channel in self.message_history:
                    history = self.message_history[channel]
                    # Show last 10 messages or all if less than 10
                    start_idx = max(0, len(history) - 10)
                    for msg in history[start_idx:]:
                        print(msg)
            
            return True
        else:
            print(f"{Colors.RED}You are not in channel {channel}. Join it first with /join {channel}{Colors.RESET}")
            return False
    
    def join_channel(self, channel):
        """Join a channel"""
        if self.send_command("JOIN", channel):
            # Add to local channel list
            with self.lock:
                self.channels.add(channel)
                if channel not in self.message_history:
                    self.message_history[channel] = []
            
            # Switch to the channel
            self.switch_channel(channel)
            return True
        return False
    
    def leave_channel(self, channel):
        """Leave a channel"""
        if self.send_command("LEAVE", channel):
            # Remove from local channel list
            with self.lock:
                if channel in self.channels:
                    self.channels.remove(channel)
                
                # Switch to default channel if leaving current
                if channel == self.current_channel:
                    if "#general" in self.channels:
                        self.switch_channel("#general")
                    elif self.channels:
                        self.switch_channel(next(iter(self.channels)))
            
            return True
        return False
    
    def receive_messages(self):
        """Receive and process messages from the server"""
        while self.connected:
            try:
                data = self.socket.recv(4096)
                if not data:
                    # Connection closed by server
                    print(f"{Colors.RED}Disconnected from server.{Colors.RESET}")
                    self.connected = False
                    break
                
                message = data.decode('utf-8')
                self.process_message(message)
                
            except Exception as e:
                if self.connected:
                    print(f"{Colors.RED}Error receiving messages: {str(e)}{Colors.RESET}")
                    self.connected = False
                break
    
    def help(self):
        """Display help information"""
        help_text = f"""
{Colors.BOLD}{Colors.GREEN}=== BetaIRC Client Help ==={Colors.RESET}
{Colors.CYAN}Available commands:{Colors.RESET}
{Colors.YELLOW}/nick <new_nick>{Colors.RESET} - Change your nickname
{Colors.YELLOW}/join <channel>{Colors.RESET} - Join a channel
{Colors.YELLOW}/leave <channel>{Colors.RESET} - Leave a channel
{Colors.YELLOW}/list [channels|#channel]{Colors.RESET} - List channels or users in a channel
{Colors.YELLOW}/msg <username> <message>{Colors.RESET} - Send private message
{Colors.YELLOW}/whois <username>{Colors.RESET} - Get information about a user
{Colors.YELLOW}/switch <channel>{Colors.RESET} - Switch to a different channel (client-side only)
{Colors.YELLOW}/quit [message]{Colors.RESET} - Disconnect from server
{Colors.YELLOW}/help{Colors.RESET} - Show this help message
{Colors.YELLOW}/clear{Colors.RESET} - Clear the screen (client-side only)

{Colors.CYAN}Messages sent without commands go to your current channel: {self.current_channel}{Colors.RESET}
"""
        print(help_text)
    
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

def main():
    """Main function to run the IRC client"""
    parser = argparse.ArgumentParser(description='BetaIRC Client')
    parser.add_argument('-s', '--server', help='Server IP address')
    parser.add_argument('-p', '--port', type=int, help='Server port')
    parser.add_argument('-u', '--username', help='Your username')
    parser.add_argument('-c', '--config', help='Load connection details from a config file')
    parser.add_argument('--save-config', help='Save connection details to a config file')
    args = parser.parse_args()
    
    # Default values
    server = '127.0.0.1'
    port = 6969
    username = args.username
    
    # Load from config file if specified
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
                server = config.get('server', server)
                port = config.get('port', port)
                username = config.get('username', username)
                print(f"{Colors.GREEN}Loaded connection details from {args.config}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error loading config file: {str(e)}{Colors.RESET}")
    
    # Command line args override config file
    if args.server:
        server = args.server
    if args.port:
        port = args.port
    
    # If no server details are provided, show interactive menu
    if not args.server and not args.port and not args.config:
        print(f"{Colors.CYAN}=== BetaIRC Client Connection Setup ==={Colors.RESET}")
        print(f"{Colors.YELLOW}1. Connect to local server (127.0.0.1:6969){Colors.RESET}")
        print(f"{Colors.YELLOW}2. Connect to a remote server{Colors.RESET}")
        
        choice = ""
        while choice not in ["1", "2"]:
            choice = input("Enter your choice (1-2): ").strip()
        
        if choice == "2":
            # Get server details
            while True:
                server_input = input(f"Enter server IP address or hostname (default: {server}): ").strip()
                if server_input:
                    server = server_input
                    
                try:
                    # Test if we can resolve the hostname
                    socket.gethostbyname(server)
                    break
                except:
                    print(f"{Colors.RED}Invalid hostname or IP address. Please try again.{Colors.RESET}")
            
            port_input = input(f"Enter server port (default: {port}): ").strip()
            if port_input:
                try:
                    port = int(port_input)
                except:
                    print(f"{Colors.YELLOW}Invalid port. Using default: {port}{Colors.RESET}")
    
    # Get username if not provided as argument or in config
    while not username or not re.match(r'^[a-zA-Z0-9_]{3,16}$', username):
        username = input("Enter your username (3-16 alphanumeric characters or underscores): ")
    
    # Save config if requested
    if args.save_config:
        try:
            config_data = {
                'server': server,
                'port': port,
                'username': username
            }
            with open(args.save_config, 'w') as f:
                json.dump(config_data, f, indent=4)
            print(f"{Colors.GREEN}Connection details saved to {args.save_config}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error saving config file: {str(e)}{Colors.RESET}")
    
    # Create and connect client
    client = IRCClient(server, port)
    
    print(f"{Colors.GREEN}Connecting to {server}:{port} as {username}...{Colors.RESET}")
    
    if client.connect(username):
        print(f"{Colors.GREEN}Connected to server! Type /help for available commands.{Colors.RESET}")
        
        # Main input loop
        try:
            while client.connected:
                user_input = input()
                
                # Skip empty input
                if not user_input.strip():
                    continue
                
                # Check for client-side commands
                if user_input.startswith('/'):
                    parts = user_input[1:].split(maxsplit=2)
                    cmd = parts[0].lower() if parts else ""
                    arg1 = parts[1] if len(parts) > 1 else ""
                    arg2 = parts[2] if len(parts) > 2 else ""
                    
                    if cmd == "help":
                        client.help()
                    elif cmd == "switch":
                        client.switch_channel(arg1)
                    elif cmd == "clear":
                        client.clear_screen()
                    elif cmd == "quit":
                        client.disconnect()
                        break
                    else:
                        # Send to server
                        client.send_message(user_input)
                else:
                    # Regular message to current channel
                    client.send_message(user_input)
        
        except KeyboardInterrupt:
            print(f"{Colors.YELLOW}Disconnecting...{Colors.RESET}")
        finally:
            client.disconnect()
    
    print(f"{Colors.RED}Disconnected. Goodbye!{Colors.RESET}")

if __name__ == "__main__":
    main()
