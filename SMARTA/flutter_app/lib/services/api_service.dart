import 'dart:convert';

import 'package:http/http.dart' as http;

class ChatReply {
  final String answer;
  final List<String> sources;

  const ChatReply({required this.answer, this.sources = const []});
}

class ApiService {
  // Desktop / Web (running the FastAPI server on the same machine)
  static String baseUrl = "http://localhost:8000";

  // Android Emulator
  // static String baseUrl = "http://10.0.2.2:8000";

  // Physical Device (replace with your machine's LAN IP)
  // static String baseUrl = "http://192.168.1.15:8000";
  static http.Client client = http.Client();

  static Future<ChatReply> sendMessage(String question) async {
    try {
      final response = await client
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

        return ChatReply(
          answer: (data["answer"] as String?) ??
              "SMARTA returned an empty response.",
          sources: (data["sources"] as List<dynamic>? ?? const [])
              .whereType<String>()
              .toList(),
        );
      }

      final body = jsonDecode(response.body);
      final detail = body is Map<String, dynamic> ? body["detail"] : null;
      return ChatReply(
        answer: detail is String
            ? detail
            : "SMARTA returned server error ${response.statusCode}.",
      );
    } catch (e) {
      return ChatReply(
        answer:
            "Unable to connect to SMARTA. Check that the API server is running.\n\n$e",
      );
    }
  }

  static Future<Map<String, dynamic>> predict({
    required String machineId,
    required String productType,
    required double airTemperature,
    required double processTemperature,
    required double rotationalSpeed,
    required double torque,
    required double toolWear,
  }) async {
    final response = await client
        .post(
          Uri.parse("$baseUrl/predict"),
          headers: {"Content-Type": "application/json"},
          body: jsonEncode({
            "machine_id": machineId,
            "observed_at": DateTime.now().toUtc().toIso8601String(),
            "features": {
              "product_type": productType,
              "air_temperature_k": airTemperature,
              "process_temperature_k": processTemperature,
              "rotational_speed_rpm": rotationalSpeed,
              "torque_nm": torque,
              "tool_wear_min": toolWear,
            },
          }),
        )
        .timeout(const Duration(seconds: 60));
    final body = jsonDecode(response.body);
    if (response.statusCode != 200 || body is! Map<String, dynamic>) {
      final detail = body is Map<String, dynamic> ? body["detail"] : null;
      throw Exception(detail ?? "Prediction failed (${response.statusCode}).");
    }
    return body;
  }

  static Future<Map<String, dynamic>> getPredictiveModelMetadata() async {
    final response = await client
        .get(Uri.parse('$baseUrl/predict/metadata'))
        .timeout(const Duration(seconds: 10));
    final body = jsonDecode(response.body);
    if (response.statusCode != 200 || body is! Map<String, dynamic>) {
      final detail = body is Map<String, dynamic> ? body['detail'] : null;
      throw Exception(
          detail ?? 'Model status unavailable (${response.statusCode}).');
    }
    return body;
  }

  /// Pings the backend's /health endpoint (defined in api.py).
  static Future<bool> pingServer() async {
    try {
      final response = await client
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
