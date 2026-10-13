import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:smarta_chat/main.dart';
import 'package:smarta_chat/screens/predict_screen.dart';
import 'package:smarta_chat/services/api_service.dart';

Map<String, dynamic> _metadata() => {
      'ready': true,
      'model_version': 'ai4i-rf-v1',
      'trained_at': '2026-10-13T09:00:00Z',
      'allowed_types': ['L', 'M', 'H'],
      'supported_failure_modes': ['TWF', 'HDF', 'PWF', 'OSF'],
      'unsupported_failure_modes': {
        'RNF': 'Only 19 positive examples; minimum is 20.'
      },
      'feature_ranges': {
        'Air temperature [K]': [295.3, 304.5],
        'Process temperature [K]': [305.7, 313.8],
        'Rotational speed [rpm]': [1168.0, 2886.0],
        'Torque [Nm]': [3.8, 76.6],
        'Tool wear [min]': [0.0, 253.0],
      },
    };

Map<String, dynamic> _predictionResponse() => {
      'prediction': {
        'machine_id': 'Machine-01',
        'prediction_timestamp': '2026-10-13T09:00:00Z',
        'model_version': 'ai4i-rf-v1',
        'machine_failure': {
          'classification': 1,
          'score': 0.78,
          'score_type': 'uncalibrated_random_forest_score',
        },
        'failure_modes': {
          'HDF': {
            'classification': 1,
            'score': 0.30,
            'score_type': 'uncalibrated_random_forest_score',
          },
        },
        'unsupported_failure_modes': {
          'RNF': 'Only 19 positive examples; minimum is 20.',
        },
        'input_features': {},
        'limitations':
            'AI4I synthetic-data classification only; not a future failure date.',
      },
      'evidence': [],
      'machine_specific_evidence': [],
      'recommendation':
          'No sufficiently supported corrective action was found in the available maintenance records or documentation. Further inspection is required.',
      'evidence_status': 'insufficient',
    };

void _setDesktopViewport(WidgetTester tester) {
  tester.view.physicalSize = const Size(1600, 1100);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('SMARTA keeps chat available and opens the prediction dashboard',
      (WidgetTester tester) async {
    _setDesktopViewport(tester);
    ApiService.client = MockClient((request) async {
      if (request.url.path.endsWith('/predict/metadata')) {
        return http.Response(jsonEncode(_metadata()), 200);
      }
      if (request.url.path.endsWith('/health')) {
        return http.Response('{"status":"ok"}', 200);
      }
      return http.Response('{}', 404);
    });
    addTearDown(ApiService.client.close);

    await tester.pumpWidget(const SmartaApp());
    await tester.pumpAndSettle();
    expect(find.text('SMARTA'), findsNWidgets(2));
    expect(find.text('Predict'), findsOneWidget);
    expect(find.text('Ask SMARTA anything'), findsOneWidget);
    await tester.tap(find.text('Predict'));
    await tester.pumpAndSettle();
    expect(find.text('Predictions Dashboard'), findsOneWidget);
    expect(find.text('Machine Simulator'), findsOneWidget);
    expect(find.text('Model ready'), findsOneWidget);
  });

  testWidgets(
      'simulator sends entered conditions and renders API response verbatim',
      (WidgetTester tester) async {
    _setDesktopViewport(tester);
    Map<String, dynamic>? submitted;
    ApiService.client = MockClient((request) async {
      if (request.url.path.endsWith('/predict/metadata')) {
        return http.Response(jsonEncode(_metadata()), 200);
      }
      if (request.url.path.endsWith('/predict')) {
        submitted = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(jsonEncode(_predictionResponse()), 200);
      }
      return http.Response('{}', 404);
    });
    addTearDown(ApiService.client.close);

    await tester.pumpWidget(const MaterialApp(home: PredictScreen()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Machine Simulator'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).at(1), '300.5');
    await tester.tap(find.text('Run Prediction'));
    await tester.pumpAndSettle();

    expect(submitted, isNotNull);
    expect(submitted!['machine_id'], 'Machine-01');
    expect(submitted!['features']['air_temperature_k'], 300.5);
    expect(submitted!['features']['product_type'], 'M');
    expect(
        find.text('Machine failure classification: Failure'), findsOneWidget);
    expect(find.text('Uncalibrated model score: 78.0%'), findsOneWidget);
    expect(find.text('Uncalibrated model score: 30.0%'), findsOneWidget);
    expect(find.textContaining('No supporting source was retrieved'),
        findsOneWidget);
    expect(find.textContaining('No sufficiently supported corrective action'),
        findsOneWidget);
    await tester.tap(find.text('Reset'));
    await tester.pumpAndSettle();
    expect(
        tester
            .widget<TextFormField>(find.byType(TextFormField).at(1))
            .controller
            ?.text,
        '298.1');
    expect(find.text('Model prediction'), findsNothing);
  });

  testWidgets(
      'simulator rejects out-of-range input before calling prediction API',
      (WidgetTester tester) async {
    _setDesktopViewport(tester);
    var predictionCalls = 0;
    ApiService.client = MockClient((request) async {
      if (request.url.path.endsWith('/predict/metadata')) {
        return http.Response(jsonEncode(_metadata()), 200);
      }
      if (request.url.path.endsWith('/predict')) predictionCalls++;
      return http.Response('{}', 404);
    });
    addTearDown(ApiService.client.close);

    await tester.pumpWidget(const MaterialApp(home: PredictScreen()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Machine Simulator'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).at(1), '310');
    await tester.tap(find.text('Run Prediction'));
    await tester.pumpAndSettle();

    expect(predictionCalls, 0);
    expect(find.textContaining('Use 295.3–304.5'), findsOneWidget);
  });

  testWidgets('RAG evidence references map to the returned source passage',
      (WidgetTester tester) async {
    _setDesktopViewport(tester);
    final response = _predictionResponse()
      ..['evidence'] = [
        {
          'source': 'manual.pdf',
          'locator': 'page 2',
          'text': 'Inspect the ventilation path for blockage.',
        },
      ]
      ..['recommendation'] = 'The manual recommends checking ventilation. [1]'
      ..['evidence_status'] = 'general_only';
    ApiService.client = MockClient((request) async {
      if (request.url.path.endsWith('/predict/metadata')) {
        return http.Response(jsonEncode(_metadata()), 200);
      }
      if (request.url.path.endsWith('/predict')) {
        return http.Response(jsonEncode(response), 200);
      }
      return http.Response('{}', 404);
    });
    addTearDown(ApiService.client.close);

    await tester.pumpWidget(const MaterialApp(home: PredictScreen()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Machine Simulator'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Run Prediction'));
    await tester.pumpAndSettle();

    expect(find.text('The manual recommends checking ventilation. [1]'),
        findsOneWidget);
    expect(find.text('manual.pdf · page 2'), findsOneWidget);
    expect(find.text('Inspect the ventilation path for blockage.'),
        findsOneWidget);
  });

  testWidgets('model and prediction API errors are visible to the user',
      (WidgetTester tester) async {
    _setDesktopViewport(tester);
    ApiService.client = MockClient((request) async => http.Response(
        '{"detail":"The predictive model is not trained."}', 503));
    addTearDown(ApiService.client.close);

    await tester.pumpWidget(const MaterialApp(home: PredictScreen()));
    await tester.pumpAndSettle();
    expect(find.text('Model unavailable'), findsOneWidget);
    await tester.tap(find.text('Machine Simulator'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Run Prediction'));
    await tester.pumpAndSettle();
    expect(find.text('Prediction unavailable'), findsOneWidget);
    expect(find.text('The predictive model is not trained.'), findsOneWidget);
  });
}
