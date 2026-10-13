class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final List<String> sources;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.sources = const [],
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
}
