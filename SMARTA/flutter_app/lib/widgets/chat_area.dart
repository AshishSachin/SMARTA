import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/chat_provider.dart';
import '../../theme.dart';
import 'chat_input.dart';
import 'message_bubble.dart';
import 'typing_indicator.dart';

class ChatArea extends StatefulWidget {
  const ChatArea({super.key});

  @override
  State<ChatArea> createState() => _ChatAreaState();
}

class _ChatAreaState extends State<ChatArea> {
  final ScrollController _scrollController = ScrollController();

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;

      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _handleSend(String text) async {
    final provider = context.read<ChatProvider>();

    _scrollToBottom();

    await provider.sendMessage(text);

    if (!mounted) return;

    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ChatProvider>();

    final messages = provider.messages;
    final isTyping = provider.isTyping;

    _scrollToBottom();

    return Column(
      children: [
        Expanded(
          child: messages.isEmpty
              ? _EmptyState(
                  onSuggestionTap: _handleSend,
                )
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(20),
                  itemCount: messages.length + (isTyping ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index == messages.length) {
                      return const TypingIndicator();
                    }

                    final message = messages[index];

                    return MessageBubble(
                      text: message.text,
                      isUser: message.isUser,
                    );
                  },
                ),
        ),
        ChatInput(
          isSending: isTyping,
          onSend: _handleSend,
        ),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  final ValueChanged<String> onSuggestionTap;

  const _EmptyState({
    required this.onSuggestionTap,
  });

  static const List<String> _suggestions = [
    "Why is the compressor tripping alarm A12?",
    "What is the recommended maintenance schedule for pump P-3?",
    "Explain the last recorded fault on line 2.",
  ];

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.smart_toy_outlined,
              size: 56,
              color: AppTheme.accent,
            ),
            const SizedBox(height: 16),
            Text(
              "Ask SMARTA anything",
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              "Your maintenance assistant, ready to help.",
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              alignment: WrapAlignment.center,
              children: _suggestions.map((suggestion) {
                return ActionChip(
                  backgroundColor: AppTheme.card,
                  label: Text(
                    suggestion,
                    style: const TextStyle(color: Colors.white),
                  ),
                  onPressed: () => onSuggestionTap(suggestion),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }
}