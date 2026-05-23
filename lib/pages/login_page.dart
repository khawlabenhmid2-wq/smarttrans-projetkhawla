import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/browser_client.dart';
import '../l10n/generated/app_localizations.dart';
import '../language_provider.dart';
import '../api_config.dart';
import 'current_user.dart';
import 'clientdashboard.dart';
import 'chauffeurdashboard.dart';
import 'admin_dashboard.dart';
import 'dart:async';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  bool isLoading = false;

  Future<void> login() async {
    final l10n = AppLocalizations.of(context)!;
    if (emailController.text.isEmpty || passwordController.text.isEmpty) {
      _showSnackBar(l10n.localeName == 'fr' ? "Veuillez remplir tous les champs" : "Please fill all fields", Colors.orange);
      return;
    }

    setState(() => isLoading = true);

    final String apiUrl = "https://smarttrans-projetkhawla.onrender.com/login";
    final client = BrowserClient();

    try {
      final response = await client.post(
        Uri.parse(apiUrl),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "email": emailController.text.trim().toLowerCase(),
          "password": passwordController.text.trim(),
        }),
      ).timeout(const Duration(seconds: 60));

      print("📡 STATUS: ${response.statusCode}");
      print("📡 BODY RAW: ${response.body}");

      if (response.body.isEmpty) {
        _showSnackBar("Serveur indisponible. Réessayez dans 30 secondes.", Colors.orange);
        return;
      }

      Map<String, dynamic> data;
      try {
        data = jsonDecode(response.body);
        print("🔴 JSON REÇU: $data"); // ← REGARDE ICI DANS LA CONSOLE
      } catch (e) {
        _showSnackBar("Réponse invalide du serveur.", Colors.orange);
        return;
      }

      if (response.statusCode == 200) {
        // ⚠️ SI LES CLÉS SONT DIFFÉRENTES, CHANGE-LES ICI APRÈS AVOIR VU LE JSON
        String nom   = (data["nom"]   as String?) ?? 
                       (data["name"]  as String?) ?? 
                       (data["prenom"] as String?) ?? "Utilisateur";
        String photo = (data["photo"] as String?) ?? "";
        int    id    = (data["id"]    as int?)    ?? 
                       (data["_id"]   as int?)    ?? 0;
        String email = (data["email"] as String?) ?? "";
        String role  = (data["role"]  as String?) ?? 
                       (data["type"]  as String?) ?? 
                       (data["user_role"] as String?) ?? "";

        print("✅ nom=$nom | role=$role | email=$email | id=$id");

        if (role.isEmpty) {
          _showSnackBar("❌ Rôle vide ! Vérifie le JSON reçu dans la console.", Colors.purple);
          return;
        }

        await CurrentUser.saveSession(email, role, id, userNom: nom, userPhoto: photo);

        print("✅ CurrentUser.role = '${CurrentUser.role}'");

        _showSnackBar("${l10n.welcome} $nom", Colors.green);

        if (!mounted) return;
        await Future.delayed(const Duration(milliseconds: 500));
        if (!mounted) return;

        if (CurrentUser.role == "client") {
          Navigator.pushReplacement(context, MaterialPageRoute(
            builder: (_) => ClientDashboard(clientId: CurrentUser.id, userEmail: CurrentUser.email)));
        } else if (CurrentUser.role == "chauffeur") {
          Navigator.pushReplacement(context, MaterialPageRoute(
            builder: (_) => ChauffeurDashboard(driverId: CurrentUser.id, userEmail: CurrentUser.email)));
        } else if (CurrentUser.role == "admin") {
          Navigator.pushReplacement(context, MaterialPageRoute(
            builder: (_) => AdminDashboard(adminEmail: CurrentUser.email)));
        } else {
          _showSnackBar("Role inconnu: '${CurrentUser.role}'", Colors.purple);
        }

      } else {
        _showSnackBar(
          (data['message'] as String?) ?? (l10n.localeName == 'fr' ? "Identifiants incorrects" : "Incorrect credentials"),
          Colors.red,
        );
      }

    } on TimeoutException {
      _showSnackBar("Serveur en démarrage, réessayez dans 30 secondes...", Colors.orange);
    } catch (e) {
      print("❌ Error: $e");
      _showSnackBar(
        l10n.localeName == 'fr' ? "Erreur: Impossible de contacter le serveur" : "Error: Could not reach server",
        Colors.red,
      );
    } finally {
      client.close();
      if (mounted) setState(() => isLoading = false);
    }
  }

  void _showSnackBar(String msg, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: color, behavior: SnackBarBehavior.floating),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final langProvider = Provider.of<LanguageProvider>(context);

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          _buildLanguageButton(context, langProvider, 'FR', 'fr'),
          _buildLanguageButton(context, langProvider, 'EN', 'en'),
          _buildLanguageButton(context, langProvider, 'AR', 'ar'),
          const SizedBox(width: 10),
        ],
      ),
      body: Center(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 450),
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 25.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.directions_bus, size: 90, color: Colors.teal),
                const SizedBox(height: 10),
                Text(l10n.appTitle, style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.teal, letterSpacing: 2.0)),
                const SizedBox(height: 40),
                TextField(
                  controller: emailController,
                  decoration: InputDecoration(
                    labelText: l10n.email,
                    prefixIcon: const Icon(Icons.email, color: Colors.teal),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                ),
                const SizedBox(height: 15),
                TextField(
                  controller: passwordController,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: l10n.password,
                    prefixIcon: const Icon(Icons.lock, color: Colors.teal),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                ),
                const SizedBox(height: 30),
                isLoading
                    ? const CircularProgressIndicator()
                    : ElevatedButton(
                        onPressed: login,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.teal,
                          minimumSize: const Size(double.infinity, 55),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: Text(l10n.login, style: const TextStyle(color: Colors.white, fontSize: 18)),
                      ),
                const SizedBox(height: 10),
                TextButton(
                  onPressed: () => Navigator.pushNamed(context, '/forgot_password'),
                  child: Text(l10n.forgotPassword, style: const TextStyle(color: Colors.teal)),
                ),
                const SizedBox(height: 10),
                TextButton(
                  onPressed: () => Navigator.pushNamed(context, '/register'),
                  child: Text(l10n.noAccount, style: const TextStyle(color: Colors.teal)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLanguageButton(BuildContext context, LanguageProvider provider, String label, String code) {
    bool isSelected = provider.locale.languageCode == code;
    return TextButton(
      onPressed: () => provider.changeLanguage(code),
      child: Text(label, style: TextStyle(
        color: isSelected ? Colors.teal : Colors.grey,
        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
      )),
    );
  }
}