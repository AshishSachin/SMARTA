import 'package:flutter/material.dart';

import '../services/api_service.dart';

class PredictScreen extends StatefulWidget {
  const PredictScreen({super.key});

  @override
  State<PredictScreen> createState() => _PredictScreenState();
}

class _PredictScreenState extends State<PredictScreen> {
  static const _defaults = <String, String>{
    'air': '298.1',
    'process': '308.6',
    'speed': '1551',
    'torque': '42.8',
    'wear': '20',
  };
  static const _fallbackRanges = <String, List<double>>{
    'Air temperature [K]': [295.3, 304.5],
    'Process temperature [K]': [305.7, 313.8],
    'Rotational speed [rpm]': [1168, 2886],
    'Torque [Nm]': [3.8, 76.6],
    'Tool wear [min]': [0, 253],
  };
  static const _failureModeNames = <String, String>{
    'TWF': 'Tool wear failure',
    'HDF': 'Heat dissipation failure',
    'PWF': 'Power failure',
    'OSF': 'Overstrain failure',
    'RNF': 'Random failure',
  };

  final _formKey = GlobalKey<FormState>();
  final _machine = TextEditingController(text: 'Machine-01');
  final _air = TextEditingController(text: _defaults['air']);
  final _process = TextEditingController(text: _defaults['process']);
  final _speed = TextEditingController(text: _defaults['speed']);
  final _torque = TextEditingController(text: _defaults['torque']);
  final _wear = TextEditingController(text: _defaults['wear']);
  late final Future<Map<String, dynamic>> _metadataFuture;
  Map<String, dynamic>? _metadata;
  String _type = 'M';
  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _result;

  @override
  void initState() {
    super.initState();
    _metadataFuture = ApiService.getPredictiveModelMetadata().then((metadata) {
      if (mounted) setState(() => _metadata = metadata);
      return metadata;
    });
  }

  @override
  void dispose() {
    for (final controller in [
      _machine,
      _air,
      _process,
      _speed,
      _torque,
      _wear,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  double? _number(String? value) => double.tryParse(value?.trim() ?? '');

  Map<String, List<double>> get _ranges {
    final raw = _metadata?['feature_ranges'];
    if (raw is! Map<String, dynamic>) return _fallbackRanges;
    return raw.map((key, value) => MapEntry(
          key,
          (value as List<dynamic>)
              .map((item) => (item as num).toDouble())
              .toList(),
        ));
  }

  String? _validateNumber(String? input, String featureName) {
    final value = _number(input);
    if (value == null || !value.isFinite) return 'Enter a valid number';
    final range = _ranges[featureName];
    if (range != null && (value < range[0] || value > range[1])) {
      return 'Use ${range[0]}–${range[1]} (training data range)';
    }
    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
      _result = null;
    });
    try {
      final response = await ApiService.predict(
        machineId: _machine.text.trim(),
        productType: _type,
        airTemperature: _number(_air.text)!,
        processTemperature: _number(_process.text)!,
        rotationalSpeed: _number(_speed.text)!,
        torque: _number(_torque.text)!,
        toolWear: _number(_wear.text)!,
      );
      if (mounted) setState(() => _result = response);
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error.toString().replaceFirst('Exception: ', ''),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _reset() {
    setState(() {
      _machine.text = 'Machine-01';
      _air.text = _defaults['air']!;
      _process.text = _defaults['process']!;
      _speed.text = _defaults['speed']!;
      _torque.text = _defaults['torque']!;
      _wear.text = _defaults['wear']!;
      _type = 'M';
      _error = null;
      _result = null;
    });
    _formKey.currentState?.reset();
  }

  Widget _numberField(
    String label,
    String featureName,
    String unit,
    TextEditingController controller,
  ) {
    final range = _ranges[featureName] ?? _fallbackRanges[featureName]!;
    return TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: InputDecoration(
        labelText: label,
        suffixText: unit,
        helperText: 'Dataset range: ${range[0]}–${range[1]} $unit',
      ),
      validator: (value) => _validateNumber(value, featureName),
      onChanged: (_) => setState(() {}),
    );
  }

  @override
  Widget build(BuildContext context) => DefaultTabController(
        length: 2,
        child: Scaffold(
          appBar: AppBar(
            title: const Text('Predictive maintenance'),
            bottom: const TabBar(
              tabs: [
                Tab(icon: Icon(Icons.dashboard_outlined), text: 'Dashboard'),
                Tab(icon: Icon(Icons.tune), text: 'Machine Simulator'),
              ],
            ),
          ),
          body: TabBarView(
            children: [
              _buildDashboard(),
              _buildSimulator(),
            ],
          ),
        ),
      );

  Widget _page(List<Widget> children) => Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 880),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: children,
          ),
        ),
      );

  Widget _buildDashboard() => _page([
        const Text(
          'Predictions Dashboard',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        const Text(
          'Model classifications are shown separately from historical evidence and generated diagnostic guidance.',
        ),
        const SizedBox(height: 16),
        FutureBuilder<Map<String, dynamic>>(
          future: _metadataFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Card(
                child: ListTile(
                  leading: SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  title: Text('Checking model readiness…'),
                ),
              );
            }
            if (snapshot.hasError) {
              return Card(
                child: ListTile(
                  leading: const Icon(Icons.error_outline),
                  title: const Text('Model unavailable'),
                  subtitle: Text(snapshot.error
                      .toString()
                      .replaceFirst('Exception: ', '')),
                ),
              );
            }
            final metadata = snapshot.data!;
            final supported =
                (metadata['supported_failure_modes'] as List<dynamic>)
                    .map((mode) => mode.toString())
                    .toList();
            final omitted =
                metadata['unsupported_failure_modes'] as Map<String, dynamic>;
            return Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.check_circle, color: Colors.green),
                        const SizedBox(width: 10),
                        const Text('Model ready',
                            style: TextStyle(fontWeight: FontWeight.bold)),
                        const Spacer(),
                        Text(metadata['model_version'].toString()),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                        'Supported failure modes: ${supported.map((mode) => '$mode — ${_failureModeNames[mode] ?? mode}').join(', ')}'),
                    if (omitted.isNotEmpty)
                      Text(
                          'Omitted: ${omitted.entries.map((entry) => '${entry.key} — ${entry.value}').join('; ')}'),
                    const SizedBox(height: 4),
                    Text(
                        'Scores are uncalibrated model scores, not calibrated probabilities.',
                        style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ),
            );
          },
        ),
        const SizedBox(height: 12),
        Card(
          child: ListTile(
            leading: const Icon(Icons.precision_manufacturing_outlined),
            title: Text(
                'Selected machine: ${_machine.text.isEmpty ? 'Not set' : _machine.text}'),
            subtitle: Text(
                'Current simulated conditions: Type $_type · Air ${_air.text} K · Process ${_process.text} K · ${_speed.text} rpm · ${_torque.text} Nm · Tool wear ${_wear.text} min'),
            trailing: TextButton(
              onPressed: () => DefaultTabController.of(context).animateTo(1),
              child: const Text('Edit'),
            ),
          ),
        ),
        const SizedBox(height: 12),
        if (_result == null)
          const Card(
            child: ListTile(
              leading: Icon(Icons.insights_outlined),
              title: Text('No prediction run yet'),
              subtitle: Text(
                  'Open Machine Simulator to submit an operating point to the API.'),
            ),
          )
        else
          _buildResults(),
      ]);

  Widget _buildSimulator() => _page([
        const Text(
          'Interactive Machine Simulator',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        const Card(
          child: ListTile(
            leading: Icon(Icons.science_outlined),
            title: Text('Simulated operating point — not live sensor data'),
            subtitle: Text(
                'SMARTA classifies the values you enter. It does not estimate a failure countdown or date.'),
          ),
        ),
        Form(
          key: _formKey,
          child: Column(
            children: [
              TextFormField(
                controller: _machine,
                decoration:
                    const InputDecoration(labelText: 'Machine identifier'),
                validator: (value) => (value?.trim().isEmpty ?? true)
                    ? 'Enter a machine identifier'
                    : null,
                onChanged: (_) => setState(() {}),
              ),
              DropdownButtonFormField<String>(
                initialValue: _type,
                decoration: const InputDecoration(labelText: 'Product type'),
                items: const [
                  DropdownMenuItem(value: 'L', child: Text('L')),
                  DropdownMenuItem(value: 'M', child: Text('M')),
                  DropdownMenuItem(value: 'H', child: Text('H')),
                ],
                onChanged: (value) => setState(() => _type = value ?? 'M'),
              ),
              _numberField('Air temperature', 'Air temperature [K]', 'K', _air),
              _numberField('Process temperature', 'Process temperature [K]',
                  'K', _process),
              _numberField(
                  'Rotational speed', 'Rotational speed [rpm]', 'rpm', _speed),
              _numberField('Torque', 'Torque [Nm]', 'Nm', _torque),
              _numberField('Tool wear', 'Tool wear [min]', 'min', _wear),
              const SizedBox(height: 18),
              Row(
                children: [
                  FilledButton.icon(
                    onPressed: _loading ? null : _submit,
                    icon: _loading
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.play_arrow),
                    label: Text(_loading ? 'Running…' : 'Run Prediction'),
                  ),
                  const SizedBox(width: 12),
                  OutlinedButton.icon(
                    onPressed: _loading ? null : _reset,
                    icon: const Icon(Icons.restart_alt),
                    label: const Text('Reset'),
                  ),
                ],
              ),
            ],
          ),
        ),
        if (_error != null)
          Card(
            color: Theme.of(context).colorScheme.errorContainer,
            child: ListTile(
              leading: const Icon(Icons.warning_amber_outlined),
              title: const Text('Prediction unavailable'),
              subtitle: Text(_error!),
            ),
          ),
        if (_result != null) ...[
          const SizedBox(height: 20),
          _buildResults(),
        ],
      ]);

  Widget _buildResults() {
    final prediction = _result!['prediction'] as Map<String, dynamic>;
    final machine = prediction['machine_failure'] as Map<String, dynamic>;
    final modes = prediction['failure_modes'] as Map<String, dynamic>;
    final evidence = _result!['evidence'] as List<dynamic>;
    final specific = _result!['machine_specific_evidence'] as List<dynamic>;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Model prediction',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                    'Machine failure classification: ${machine['classification'] == 1 ? 'Failure' : 'No failure'}',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
                Text(
                    'Uncalibrated model score: ${((machine['score'] as num) * 100).toStringAsFixed(1)}%'),
                Text(
                    'Model ${prediction['model_version']} · ${prediction['prediction_timestamp']}'),
                const Divider(),
                const Text('Failure-mode outputs',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                for (final entry in modes.entries)
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: Text(
                        '${entry.key} — ${_failureModeNames[entry.key] ?? entry.key}'),
                    subtitle: Text(
                        'Uncalibrated model score: ${((entry.value['score'] as num) * 100).toStringAsFixed(1)}%'),
                    trailing: Text(entry.value['classification'] == 1
                        ? 'Classified'
                        : 'Not classified'),
                  ),
                Text(prediction['limitations'].toString(),
                    style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Text('RAG diagnostic explanation',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(_result!['recommendation'].toString()),
                const SizedBox(height: 8),
                Text('Evidence status: ${_result!['evidence_status']}'),
                if (specific.isEmpty && evidence.isNotEmpty)
                  const Text(
                      'No exact machine-specific record matched; the sources below are general evidence.'),
                if (evidence.isEmpty)
                  const Text(
                      'No supporting source was retrieved. No corrective action is asserted.'),
                for (var index = 0; index < evidence.length; index++)
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    leading: Text('[${index + 1}]'),
                    title: Text(
                        '${evidence[index]['source']} · ${evidence[index]['locator']}'),
                    subtitle: Text(evidence[index]['text'].toString()),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
