import 'package:flutter/material.dart';

void main() => runApp(const TraderApp());

class TraderApp extends StatelessWidget {
  const TraderApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'AI Options Trader',
    theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
    home: const HomePage(),
  );
}

class HomePage extends StatelessWidget {
  const HomePage({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('AI Options Trader')),
    body: ListView(padding: const EdgeInsets.all(16), children: [
      const Card(child: ListTile(
        title: Text('Paper trading mode'),
        subtitle: Text('Angel One connection and live orders are disabled'),
        leading: Icon(Icons.shield_outlined),
      )),
      const Card(child: ListTile(title: Text('Starting capital'), trailing: Text('₹25,000'))),
      const Card(child: ListTile(title: Text('Market universe'), subtitle: Text('NIFTY · BANKNIFTY · FINNIFTY · MIDCPNIFTY · SENSEX · BANKEX'))),
      const Card(child: ListTile(title: Text('Modules'), subtitle: Text('Backtesting · Options chain · Paper orders · Risk controls'))),
      const Padding(padding: EdgeInsets.only(top: 16), child: Text(
        'Android UI scaffold. Configure the secure backend API URL and implement authenticated API calls before operational use.',
      )),
    ]),
  );
}
