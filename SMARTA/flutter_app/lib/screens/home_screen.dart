import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/chat_provider.dart';
import '../../theme.dart';
import '../../widgets/chat_area.dart';
import '../../widgets/right_panel.dart';
import '../../widgets/sidebar.dart';
import 'predict_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => ChatProvider(),
      child: Scaffold(
        appBar: AppBar(
          title: Row(
            children: [
              const Text("SMARTA"),
              const SizedBox(width: 12),
              Consumer<ChatProvider>(
                builder: (context, provider, _) {
                  final connected = provider.serverStatus == "Connected";

                  return Row(
                    children: [
                      Icon(
                        Icons.circle,
                        color: connected ? AppTheme.success : AppTheme.danger,
                        size: 10,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        provider.serverStatus,
                        style: TextStyle(
                          fontSize: 13,
                          color: connected ? AppTheme.success : AppTheme.danger,
                        ),
                      ),
                    ],
                  );
                },
              ),
            ],
          ),
          actions: [
            TextButton.icon(
              onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                      builder: (_) => const PredictScreen())),
              icon: const Icon(Icons.analytics_outlined),
              label: const Text('Predict'),
            ),
            const SizedBox(width: 12),
          ],
        ),
        body: const Row(
          children: [
            Sidebar(),
            VerticalDivider(
              width: 1,
              color: Colors.white10,
            ),
            Expanded(
              child: ChatArea(),
            ),
            VerticalDivider(
              width: 1,
              color: Colors.white10,
            ),
            RightPanel(),
          ],
        ),
      ),
    );
  }
}
