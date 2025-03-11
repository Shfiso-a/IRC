# BetaIRC - Custom IRC Protocol Implementation

A modern IRC (Internet Relay Chat) server and client

## Features

- Multiple channels with user management
- Private messaging
- Channel topics
- Admin commands (kick, ban)
- User information and status
- Colored terminal interface
- Message history for channels

### Message Format

All messages follow this JSON structure:

```json
{
  "sender": "username",
  "type": "channel|private|system",
  "recipient": "channel_name|username|all",
  "content": "message text",
  "timestamp": 1234567890
}
```

### Command Structure

Commands are prefixed with `/` and follow this pattern:
```
/COMMAND [TARGET] [CONTENT]
```

For example:
- `/JOIN #general` - Join the #general channel
- `/MSG user1 Hello there!` - Send a private message to user1
- `/NICK newname` - Change your nickname to newname

### Response Format

Server responses use this format:
```json
{
  "code": "200|400|401|403|404",
  "message": "Response text",
  "timestamp": 1234567890
}
```

### Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| NICK | Change nickname | `/NICK newname` |
| JOIN | Join a channel | `/JOIN #channel` |
| LEAVE | Leave a channel | `/LEAVE #channel` |
| LIST | List channels or users | `/LIST channels` or `/LIST #channel` |
| MSG | Send a private message | `/MSG username message` |
| WHOIS | Get user information | `/WHOIS username` |
| KICK | Kick a user (admin only) | `/KICK username reason` |
| BAN | Ban a user (admin only) | `/BAN username reason` |
| QUIT | Disconnect from server | `/QUIT goodbye message` |
| HELP | Show help information | `/HELP` |

## Getting Started

### Server Setup

1. Make sure you have Python 3.6+ installed
2. Run the server:
   ```
   python server.py
   ```
   
By default, the server runs on 127.0.0.1:6969.

### Client Usage

1. Run the client:
   ```
   python client.py
   ```
   
2. Or specify server details:
   ```
   python client.py --server 192.168.1.100 --port 6969 --username YourName
   ```

3. Once connected, you'll automatically join the #general channel
4. Type `/help` to see available commands
5. Use the `/switch` command to change between joined channels
6. Messages typed without a command prefix are sent to your current channel

## Client-Side Commands

The client supports some additional commands not sent to the server:

- `/switch #channel` - Switch to a different joined channel
- `/clear` - Clear the terminal screen
- `/help` - Show help information

## Examples

Join a channel and send a message:
```
/join #programming
Hello everyone! I'm new here.
```

Send a private message:
```
/msg alice Hey Alice, how are you doing?
```

Change your nickname:
```
/nick SuperUser
```

Get information about a user:
```
/whois bob
```

## Advanced Setup

For a more permanent setup, you might want to:

1. Run the server as a service
2. Configure a custom host/port
3. Add authentication
4. Set up logging to a file

## License

This project is open source.

## Contributing

Contributions welcome! Feel free to submit issues and pull requests. 
