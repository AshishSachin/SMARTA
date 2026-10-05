import 'chat_message.dart';

class ChatSession {
  String id;
  String title;
  List<ChatMessage> messages;

  ChatSession({
    required this.id,
    required this.title,
    List<ChatMessage>? messages,
  }) : messages = messages ?? [];
}