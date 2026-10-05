import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/chat_session.dart';
import '../providers/chat_provider.dart';
import '../../theme.dart';

class Sidebar extends StatelessWidget {
  const Sidebar({super.key});

  Future<void> _renameDialog(
    BuildContext context,
    ChatProvider provider,
    ChatSession session,
  ) async {
    final controller = TextEditingController(text: session.title);

    final newTitle = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: AppTheme.card,
          title: const Text("Rename Chat"),
          content: TextField(
            controller: controller,
            autofocus: true,
            decoration: const InputDecoration(
              hintText: "Chat title",
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text("Cancel"),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(
                  context,
                  controller.text.trim(),
                );
              },
              child: const Text("Save"),
            ),
          ],
        );
      },
    );

    if (newTitle != null && newTitle.isNotEmpty) {
      provider.renameChat(session.id, newTitle);
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ChatProvider>();

    final sessions = provider.sessions;
    final activeId = provider.activeSession.id;

    return Container(
      width: 280,
      color: AppTheme.sidebar,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                const Icon(
                  Icons.bolt,
                  color: AppTheme.accent,
                  size: 26,
                ),
                const SizedBox(width: 8),
                Text(
                  "SMARTA",
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ],
            ),
          ),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: provider.newChat,
                icon: const Icon(
                  Icons.add,
                  size: 18,
                ),
                label: const Text("New Chat"),
              ),
            ),
          ),

          const SizedBox(height: 12),
          const Divider(height: 1),

          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: sessions.length,
              itemBuilder: (context, index) {
                final session = sessions[index];
                final isActive = session.id == activeId;

                return Container(
                  margin: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: isActive
                        ? AppTheme.card2
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: ListTile(
                    dense: true,
                    leading: const Icon(
                      Icons.chat_bubble_outline,
                      size: 18,
                      color: AppTheme.textSecondary,
                    ),
                    title: Text(
                      session.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 14,
                      ),
                    ),
                    onTap: () {
                      provider.selectChat(session.id);
                    },
                    trailing: PopupMenuButton<String>(
                      color: AppTheme.card,
                      icon: const Icon(
                        Icons.more_vert,
                        size: 18,
                        color: AppTheme.textSecondary,
                      ),
                      onSelected: (value) {
                        if (value == "rename") {
                          _renameDialog(
                            context,
                            provider,
                            session,
                          );
                        }

                        if (value == "delete") {
                          provider.deleteChat(session.id);
                        }
                      },
                      itemBuilder: (context) => const [
                        PopupMenuItem(
                          value: "rename",
                          child: Text("Rename"),
                        ),
                        PopupMenuItem(
                          value: "delete",
                          child: Text("Delete"),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}