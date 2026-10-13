import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/chat_provider.dart';
import '../../theme.dart';

class RightPanel extends StatelessWidget {
  const RightPanel({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ChatProvider>();
    final connected = provider.serverStatus == "Connected";
    final messageCount = provider.messages.length;

    return Container(
      width: 300,
      color: AppTheme.sidebar,
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            "Status",
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Icon(
                    Icons.circle,
                    color: connected ? AppTheme.success : AppTheme.danger,
                    size: 12,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      provider.serverStatus,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: connected ? AppTheme.success : AppTheme.danger,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  IconButton(
                    tooltip: "Refresh",
                    icon: const Icon(
                      Icons.refresh,
                      size: 18,
                    ),
                    onPressed: provider.refreshServerStatus,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            "Session Info",
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _InfoRow(
                    label: "Active Chat",
                    value: provider.activeSession.title,
                  ),
                  const SizedBox(height: 10),
                  _InfoRow(
                    label: "Messages",
                    value: "$messageCount",
                  ),
                  const SizedBox(height: 10),
                  _InfoRow(
                    label: "Total Chats",
                    value: "${provider.sessions.length}",
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.right,
            overflow: TextOverflow.ellipsis,
            maxLines: 1,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
      ],
    );
  }
}
