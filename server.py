import socket
import threading
import time
import json
import re
import logging
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BetaIRC')

class IRCProtocol:
    """Custom IRC Protocol Definition"""
    
    # Command prefixes
    CMD_PREFIX = "/"
    
    # Command definitions
    CMD_NICK = "NICK"          # Change nickname
    CMD_JOIN = "JOIN"          # Join a channel
    CMD_LEAVE = "LEAVE"        # Leave a channel
    CMD_LIST = "LIST"          # List channels or users
    CMD_MSG = "MSG"            # Private message
    CMD_WHOIS = "WHOIS"        # Get user info
    CMD_KICK = "KICK"          # Kick a user (admin only)
    CMD_BAN = "BAN"            # Ban a user (admin only)
    CMD_QUIT = "QUIT"          # Disconnect from server
    CMD_HELP = "HELP"          # Show help
    
    # Response codes
    RESP_OK = "200"            # OK response
    RESP_ERROR = "400"         # General error
    RESP_AUTH_REQUIRED = "401" # Authentication required
    RESP_FORBIDDEN = "403"     # Forbidden action
    RESP_NOT_FOUND = "404"     # Channel/user not found
    
    # Message formatting
    @staticmethod
    def format_message(sender, message_type, recipient, content):
        """Format a message according to protocol"""
        timestamp = int(time.time())
        message = {
            "sender": sender,
            "type": message_type,  # "channel", "private", "system"
            "recipient": recipient,
            "content": content,
            "timestamp": timestamp
        }
        return json.dumps(message)
    
    @staticmethod
    def parse_command(message):
        """Parse a command message"""
        if not message.startswith(IRCProtocol.CMD_PREFIX):
            return None, None, None
            
        parts = message[1:].split(maxsplit=2)
        command = parts[0].upper() if parts else ""
        target = parts[1] if len(parts) > 1 else ""
        content = parts[2] if len(parts) > 2 else ""
        
        return command, target, content
    
    @staticmethod
    def format_response(code, message):
        """Format a server response"""
        return json.dumps({
            "code": code,
            "message": message,
            "timestamp": int(time.time())
        })

class IRCServer:
    def __init__(self, host='0.0.0.0', port=6969):
        """Initialize the IRC server
        
        Args:
            host (str): IP address to bind to. Use '0.0.0.0' to listen on all interfaces.
            port (int): Port number to listen on
        """
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen(5)
        
        # Client management
        self.clients = []  # All connected client sockets
        self.usernames = {}  # Maps socket to username
        self.user_info = {}  # Additional user information
        
        # Channel management
        self.channels = {
            "#general": {"users": set(), "topic": "General discussion", "created_at": int(time.time())},
            "#help": {"users": set(), "topic": "Get help with the server", "created_at": int(time.time())}
        }
        
        # Server attributes
        self.name = "BetaIRC"
        self.version = "1.0.0"
        self.created_at = int(time.time())
        self.admins = ["admin"]  # Admin usernames
        
        logger.info(f"Server initialized on {host}:{port}")

    def broadcast_to_channel(self, channel, message, exclude=None):
        """Send a message to all users in a channel"""
        if channel not in self.channels:
            return
            
        for user_socket in self.clients:
            username = self.usernames.get(user_socket)
            if username and username in self.channels[channel]["users"] and user_socket != exclude:
                try:
                    user_socket.send(message.encode('utf-8'))
                except:
                    self.disconnect_client(user_socket)

    def broadcast(self, message):
        """Send a message to all connected clients"""
        for client in self.clients:
            try:
                client.send(message.encode('utf-8'))
            except:
                self.disconnect_client(client)
    
    def send_to_user(self, username, message):
        """Send a message to a specific user"""
        for client, name in self.usernames.items():
            if name == username:
                try:
                    client.send(message.encode('utf-8'))
                    return True
                except:
                    self.disconnect_client(client)
                    return False
        return False
    
    def disconnect_client(self, client_socket):
        """Safely disconnect a client and clean up resources"""
        username = self.usernames.get(client_socket)
        
        if username:
            # Remove user from all channels
            for channel in self.channels:
                if username in self.channels[channel]["users"]:
                    self.channels[channel]["users"].remove(username)
            
            # Clean up user data
            del self.usernames[client_socket]
            if username in self.user_info:
                del self.user_info[username]
            
            # Notify others
            leave_message = IRCProtocol.format_message("SERVER", "system", "all", f"{username} has left the server.")
            self.broadcast(leave_message)
            logger.info(f"User {username} has disconnected")
        
        # Remove from clients list
        if client_socket in self.clients:
            self.clients.remove(client_socket)
        
        # Close socket
        try:
            client_socket.close()
        except:
            pass

    def handle_command(self, client_socket, command, target, content):
        """Handle a protocol command"""
        username = self.usernames.get(client_socket)
        
        if not username:
            return
            
        if command == IRCProtocol.CMD_NICK:
            # Validate new nickname
            new_nick = target.strip()
            if not new_nick or not re.match(r'^[a-zA-Z0-9_]{3,16}$', new_nick):
                response = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, "Invalid nickname. Use 3-16 alphanumeric characters or underscores.")
                client_socket.send(response.encode('utf-8'))
                return
                
            # Check if nickname is taken
            if new_nick in self.usernames.values():
                response = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, "Nickname already in use.")
                client_socket.send(response.encode('utf-8'))
                return
                
            # Update nickname
            old_nick = username
            self.usernames[client_socket] = new_nick
            
            # Update user in channels
            for channel in self.channels:
                if old_nick in self.channels[channel]["users"]:
                    self.channels[channel]["users"].remove(old_nick)
                    self.channels[channel]["users"].add(new_nick)
            
            # Notify everyone
            nick_message = IRCProtocol.format_message("SERVER", "system", "all", f"{old_nick} is now known as {new_nick}")
            self.broadcast(nick_message)
            
        elif command == IRCProtocol.CMD_JOIN:
            channel = target.strip()
            
            # Ensure channel name starts with #
            if not channel.startswith("#"):
                channel = f"#{channel}"
                
            # Create channel if it doesn't exist
            if channel not in self.channels:
                self.channels[channel] = {
                    "users": set(),
                    "topic": f"Welcome to {channel}",
                    "created_at": int(time.time())
                }
                
            # Add user to channel
            self.channels[channel]["users"].add(username)
            
            # Notify channel
            join_message = IRCProtocol.format_message("SERVER", "system", channel, f"{username} has joined {channel}")
            self.broadcast_to_channel(channel, join_message)
            
            # Send channel info to user
            topic_message = IRCProtocol.format_message("SERVER", "system", username, f"Topic for {channel}: {self.channels[channel]['topic']}")
            client_socket.send(topic_message.encode('utf-8'))
            
            users_message = IRCProtocol.format_message("SERVER", "system", username, f"Users in {channel}: {', '.join(self.channels[channel]['users'])}")
            client_socket.send(users_message.encode('utf-8'))
            
        elif command == IRCProtocol.CMD_LEAVE:
            channel = target.strip()
            
            # Ensure channel name starts with #
            if not channel.startswith("#"):
                channel = f"#{channel}"
                
            # Check if channel exists
            if channel not in self.channels:
                response = IRCProtocol.format_response(IRCProtocol.RESP_NOT_FOUND, f"Channel {channel} not found.")
                client_socket.send(response.encode('utf-8'))
                return
                
            # Check if user is in the channel
            if username not in self.channels[channel]["users"]:
                response = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, f"You are not in {channel}.")
                client_socket.send(response.encode('utf-8'))
                return
                
            # Remove user from channel
            self.channels[channel]["users"].remove(username)
            
            # Notify channel
            leave_message = IRCProtocol.format_message("SERVER", "system", channel, f"{username} has left {channel}")
            self.broadcast_to_channel(channel, leave_message)
            
            # Cleanup empty channels (except default ones)
            if len(self.channels[channel]["users"]) == 0 and channel not in ["#general", "#help"]:
                del self.channels[channel]
                
        elif command == IRCProtocol.CMD_LIST:
            if not target or target == "channels":
                # List all channels
                channel_list = []
                for chan_name, chan_data in self.channels.items():
                    channel_list.append(f"{chan_name} ({len(chan_data['users'])} users) - {chan_data['topic']}")
                
                channels_message = IRCProtocol.format_message("SERVER", "system", username, "Available channels:\n" + "\n".join(channel_list))
                client_socket.send(channels_message.encode('utf-8'))
                
            elif target.startswith("#"):
                # List users in a specific channel
                channel = target
                
                if channel not in self.channels:
                    response = IRCProtocol.format_response(IRCProtocol.RESP_NOT_FOUND, f"Channel {channel} not found.")
                    client_socket.send(response.encode('utf-8'))
                    return
                    
                users_message = IRCProtocol.format_message("SERVER", "system", username, 
                    f"Users in {channel} ({len(self.channels[channel]['users'])}): {', '.join(sorted(self.channels[channel]['users']))}")
                client_socket.send(users_message.encode('utf-8'))
                
            else:
                # List all users
                users_message = IRCProtocol.format_message("SERVER", "system", username, 
                    f"Connected users ({len(self.usernames)}): {', '.join(sorted(self.usernames.values()))}")
                client_socket.send(users_message.encode('utf-8'))
                
        elif command == IRCProtocol.CMD_MSG:
            # Private messaging
            recipient = target.strip()
            
            if not recipient or not content:
                response = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, "Usage: /msg <username> <message>")
                client_socket.send(response.encode('utf-8'))
                return
                
            # Check if recipient exists
            if recipient not in self.usernames.values():
                response = IRCProtocol.format_response(IRCProtocol.RESP_NOT_FOUND, f"User {recipient} not found.")
                client_socket.send(response.encode('utf-8'))
                return
                
            # Send private message
            private_message = IRCProtocol.format_message(username, "private", recipient, content)
            
            # Send to recipient
            if self.send_to_user(recipient, private_message):
                # Send confirmation to sender
                confirm_message = IRCProtocol.format_message("SERVER", "system", username, f"Message sent to {recipient}")
                client_socket.send(confirm_message.encode('utf-8'))
            else:
                response = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, f"Failed to send message to {recipient}")
                client_socket.send(response.encode('utf-8'))
                
        elif command == IRCProtocol.CMD_WHOIS:
            # Get info about a user
            target_user = target.strip()
            
            if not target_user:
                response = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, "Usage: /whois <username>")
                client_socket.send(response.encode('utf-8'))
                return
                
            # Check if user exists
            if target_user not in self.usernames.values():
                response = IRCProtocol.format_response(IRCProtocol.RESP_NOT_FOUND, f"User {target_user} not found.")
                client_socket.send(response.encode('utf-8'))
                return
                
            # Get user's channels
            user_channels = []
            for chan_name, chan_data in self.channels.items():
                if target_user in chan_data["users"]:
                    user_channels.append(chan_name)
                    
            # Get user info
            user_info = self.user_info.get(target_user, {})
            connected_since = user_info.get("connected_at", "unknown")
            
            # Send user info
            info_message = IRCProtocol.format_message("SERVER", "system", username, 
                f"User: {target_user}\nChannels: {', '.join(user_channels)}\nConnected since: {connected_since}")
            client_socket.send(info_message.encode('utf-8'))
            
        elif command == IRCProtocol.CMD_KICK or command == IRCProtocol.CMD_BAN:
            # Admin commands
            if username not in self.admins:
                response = IRCProtocol.format_response(IRCProtocol.RESP_FORBIDDEN, "You don't have permission to use this command.")
                client_socket.send(response.encode('utf-8'))
                return
                
            # Implementation for kick/ban would go here
            # (Omitted for brevity but would involve finding the user's socket and disconnecting them)
            pass
            
        elif command == IRCProtocol.CMD_QUIT:
            # Disconnect user
            quit_message = content if content else "Leaving"
            system_message = IRCProtocol.format_message(username, "system", "all", f"has quit: {quit_message}")
            self.broadcast(system_message)
            self.disconnect_client(client_socket)
            
        elif command == IRCProtocol.CMD_HELP:
            # Send help information
            help_message = IRCProtocol.format_message("SERVER", "system", username, 
                "Available commands:\n"
                "/nick <new_nickname> - Change your nickname\n"
                "/join <channel> - Join a channel\n"
                "/leave <channel> - Leave a channel\n"
                "/list [channels|#channel] - List channels or users in a channel\n"
                "/msg <username> <message> - Send private message\n"
                "/whois <username> - Get information about a user\n"
                "/quit [message] - Disconnect from server\n"
                "/help - Show this help message")
            client_socket.send(help_message.encode('utf-8'))
            
        else:
            # Unknown command
            response = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, f"Unknown command: {command}")
            client_socket.send(response.encode('utf-8'))

    def handle_client(self, client_socket):
        """Handle client connection and messages"""
        try:
            # First message is the username
            username_data = client_socket.recv(1024).decode('utf-8').strip()
            
            # Parse as JSON if possible, otherwise treat as plain username
            try:
                data = json.loads(username_data)
                username = data.get("username", "")
            except:
                username = username_data
            
            # Validate username
            if not username or not re.match(r'^[a-zA-Z0-9_]{3,16}$', username):
                error_message = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, "Invalid username. Use 3-16 alphanumeric characters or underscores.")
                client_socket.send(error_message.encode('utf-8'))
                client_socket.close()
                return
                
            # Check if username is taken
            if username in self.usernames.values():
                error_message = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, "Username already in use. Please choose another one.")
                client_socket.send(error_message.encode('utf-8'))
                client_socket.close()
                return
            
            # Register user
            self.usernames[client_socket] = username
            
            # Store user info
            self.user_info[username] = {
                "connected_at": int(time.time()),
                "ip": client_socket.getpeername()[0]
            }
            
            # Add to default channel
            self.channels["#general"]["users"].add(username)
            
            # Welcome message
            welcome_message = IRCProtocol.format_message("SERVER", "system", username, 
                f"Welcome to {self.name} v{self.version}! There are {len(self.usernames)} users online.\n"
                f"Type /help for available commands.")
            client_socket.send(welcome_message.encode('utf-8'))
            
            # Notify everyone
            join_message = IRCProtocol.format_message("SERVER", "system", "all", f"{username} has joined the server")
            self.broadcast(join_message)
            
            # Notify general channel
            channel_join = IRCProtocol.format_message("SERVER", "system", "#general", f"{username} has joined #general")
            self.broadcast_to_channel("#general", channel_join)
            
            logger.info(f"User {username} connected from {client_socket.getpeername()[0]}")
            
            # Main message loop
            while True:
                message_data = client_socket.recv(4096)
                if not message_data:
                    break
                
                message_str = message_data.decode('utf-8')
                
                # Check if it's a command
                command, target, content = IRCProtocol.parse_command(message_str)
                
                if command:
                    # Handle protocol command
                    self.handle_command(client_socket, command, target, content)
                else:
                    # Regular message - determine which channels it should go to
                    user_channels = []
                    for channel, data in self.channels.items():
                        if username in data["users"]:
                            user_channels.append(channel)
                    
                    if user_channels:
                        # Default to #general if user is in it
                        target_channel = "#general" if "#general" in user_channels else user_channels[0]
                        
                        # Format and send message to the channel
                        formatted_message = IRCProtocol.format_message(username, "channel", target_channel, message_str)
                        self.broadcast_to_channel(target_channel, formatted_message)
                    else:
                        # User is not in any channel
                        error_message = IRCProtocol.format_response(IRCProtocol.RESP_ERROR, "You are not in any channel. Join a channel first.")
                        client_socket.send(error_message.encode('utf-8'))
        
        except Exception as e:
            logger.error(f"Error handling client: {str(e)}")
        finally:
            self.disconnect_client(client_socket)

    def run(self):
        """Run the IRC server"""
        logger.info(f"{self.name} v{self.version} started...")
        try:
            while True:
                client_socket, addr = self.server.accept()
                logger.info(f"Connection from {addr}")
                self.clients.append(client_socket)
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
        finally:
            # Close all client connections
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            
            # Close server socket
            self.server.close()
            logger.info("Server stopped")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='BetaIRC Server')
    parser.add_argument('-H', '--host', default='0.0.0.0', 
                        help='IP address to bind to (default: 0.0.0.0, which binds to all interfaces)')
    parser.add_argument('-p', '--port', type=int, default=6969,
                        help='Port to listen on (default: 6969)')
    parser.add_argument('-c', '--config', help='Path to config file')
    parser.add_argument('-l', '--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the logging level')
    parser.add_argument('-a', '--admin', nargs='+', help='Set admin usernames')
    args = parser.parse_args()
    
    # Load config from file if specified
    config = {}
    if args.config:
        try:
            import json
            with open(args.config, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {args.config}")
        except Exception as e:
            logger.error(f"Error loading config file: {str(e)}")
    
    # Set log level
    log_level = args.log_level
    if 'log_level' in config:
        log_level = config.get('log_level', log_level)
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    # Get server settings
    host = args.host
    if 'host' in config:
        host = config.get('host', host)
        
    port = args.port
    if 'port' in config:
        port = config.get('port', port)
    
    # Create and run server
    server = IRCServer(host, port)
    
    # Set admins
    if args.admin:
        server.admins = args.admin
    elif 'admins' in config:
        server.admins = config.get('admins', server.admins)
    
    # Show network interfaces to help with connection
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        def get_public_ip():
            try:
                import urllib.request
                external_ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
                return external_ip
            except:
                return "Could not determine"
        
        logger.info(f"Server hostname: {hostname}")
        logger.info(f"Local IP address: {local_ip}")
        
        if host == "0.0.0.0":
            logger.info(f"Public IP address: {get_public_ip()}")
            logger.info(f"Clients can connect using any of these IP addresses on port {port}")
            logger.info("If connecting from the internet, make sure port forwarding is configured on your router")
    except:
        pass
    
    # Run the server
    server.run()