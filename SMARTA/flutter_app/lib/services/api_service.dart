import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

class ApiService {
  // Desktop / Web (running the FastAPI server on the same machine)
  static String baseUrl = "http://localhost:8000";

  // Android Emulator
  // static String baseUrl = "http://10.0.2.2:8000";

  // Physical Device (replace with your machine's LAN IP)
  // static String baseUrl = "http://192.168.1.15:8000";

  static Future<String> sendMessage(String question) async {
    try {
      final response = await http
          .post(
            Uri.parse("$baseUrl/chat"),
            headers: {
              "Content-Type": "application/json",
            },
            body: jsonEncode({
              "question": question,
            }),
          )
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;

        return (data["answer"] as String?) ??
            "SMARTA returned an empty response.";
      }

      return "Server Error (${response.statusCode})";
    } on SocketException {
      return "Unable to connect to SMARTA.\n\nIs the FastAPI server running?";
    } catch (e) {
      return "Unable to connect to SMARTA.\n\n$e";
    }
  }

  /// Pings the backend's /health endpoint (defined in api.py).
  static Future<bool> pingServer() async {
    try {
      final response = await http
          .get(Uri.parse("$baseUrl/health"))
          .timeout(const Duration(seconds: 5));

      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  static Future<String> getServerStatus() async {
    final online = await pingServer();

    return online ? "Connected" : "Disconnected";
  }

  static void changeServer(String url) {
    baseUrl = url;
  }
}