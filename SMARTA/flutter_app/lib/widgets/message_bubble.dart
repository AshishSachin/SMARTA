import 'package:flutter/material.dart';

import '../../theme.dart';

class MessageBubble extends StatelessWidget {
  final String text;
  final bool isUser;
  final List<String> sources;

  const MessageBubble({
    super.key,
    required this.text,
    required this.isUser,
    this.sources = const [],
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(
          maxWidth: 640,
        ),
        margin: const EdgeInsets.symmetric(
          vertical: 6,
        ),
        padding: const EdgeInsets.symmetric(
          horizontal: 18,
          vertical: 14,
        ),
        decoration: BoxDecoration(
          color: isUser ? AppTheme.accent : AppTheme.card,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(isUser ? 18 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 18),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            SelectableText(
              text,
              style: TextStyle(
                color: isUser ? Colors.white : AppTheme.textPrimary,
                fontSize: 15,
                height: 1.4,
              ),
            ),
            if (!isUser && sources.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                'Sources: ${sources.join(' · ')}',
                style: TextStyle(
                  color: AppTheme.textPrimary.withValues(alpha: 0.7),
                  fontSize: 11,
                  height: 1.3,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
