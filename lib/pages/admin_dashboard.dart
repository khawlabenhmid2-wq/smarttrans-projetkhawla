import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';
import 'package:provider/provider.dart';
import '../l10n/generated/app_localizations.dart';
import '../language_provider.dart';

// --- Imports ---
import 'bus_list_page.dart';
import 'ligne_list_page.dart';
import 'incident_list_page.dart';
import 'avis_admin_page.dart';
import 'performance_chauffeur_page.dart';
import 'AdminAddParcoursPage.dart';
import 'profile_page.dart';
import 'Admin_Chauffeur_List_Page.dart'; // <--- زدنا الـ Import متاع الصفحة الجديدة
import 'AdminParcoursListPage.dart'; // Import the new list page
import 'admin_nlp_report_page.dart';
import 'client_ai_dashboard_page.dart';
import 'admin_historique_page.dart';
import 'current_user.dart';
import '../api_config.dart';


class AdminDashboard extends StatefulWidget {
  final String adminEmail;

  AdminDashboard({required this.adminEmail});
  @override
  _AdminDashboardState createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> {
  int busCount = 0;
  int ligneCount = 0;
  int chauffeurCount = 0;
  int incidentCount = 0;
  bool isLoading = true;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    fetchStats();
    _timer = Timer.periodic(Duration(seconds: 30), (timer) => fetchStats());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> fetchStats() async {
    try {
      final response = await http.get(Uri.parse('${ApiConfig.baseUrl}/get_counts'));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (mounted) {
          setState(() {
            busCount = data['bus'] ?? 0;
            ligneCount = data['lignes'] ?? 0;
            chauffeurCount = data['chauffeurs'] ?? 0;
            incidentCount = data['incidents'] ?? 0;
            isLoading = false;
          });
        }
      }
    } catch (e) {
      print("Erreur Stats: $e");
      if (mounted) setState(() => isLoading = false);
    }
  }

  Widget _buildDrawerItem(IconData icon, String title, Widget? destinationPage, {Color color = Colors.black87}) {
    return ListTile(
      leading: Icon(icon, color: color),
      title: Text(title),
      onTap: () {
        Navigator.pop(context); 
        if (destinationPage != null) {
          Navigator.push(context, MaterialPageRoute(builder: (context) => destinationPage));
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[100],
      appBar: AppBar(
        title: Text("${AppLocalizations.of(context)!.appTitle} Admin"),
        backgroundColor: Colors.teal,
        elevation: 0,
        actions: [IconButton(icon: Icon(Icons.refresh), onPressed: fetchStats)],
      ),
      drawer: Drawer(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            UserAccountsDrawerHeader(
              decoration: BoxDecoration(color: Colors.teal),
              accountName: Text("Admin ", style: TextStyle(fontWeight: FontWeight.bold)),
              accountEmail: Text(widget.adminEmail),
              currentAccountPicture: GestureDetector(
                onTap: () {
                  Navigator.pop(context);
                 Navigator.push(context, MaterialPageRoute(builder: (context) => ProfilePage (userEmail: widget.adminEmail)));
                },
                child: CircleAvatar(
                  backgroundColor: Colors.white,
                  child: Icon(Icons.admin_panel_settings, color: Colors.teal, size: 35),
                ),
              ),
            ),
            _buildDrawerItem(Icons.map, "Gestion des Lignes", LigneListPage()),
            _buildDrawerItem(Icons.directions_bus, "Gestion des Bus", BusListPage()),
            _buildDrawerItem(Icons.person, "Gestion des Chauffeurs", AdminChauffeurListPage()),
            _buildDrawerItem(Icons.add_task, "Gestion des Parcours", AdminParcoursListPage()),
            
            // --- تعديل الـ Affectations هنا ---
            
            
            Divider(),
            _buildDrawerItem(Icons.history, "Historique des Parcours", AdminHistoriquePage()),
            _buildDrawerItem(Icons.report_problem, "Incidents", IncidentListPage(), color: Colors.red),
           // _buildDrawerItem(Icons.psychology, "Analyse AI & Avis", AvisAdminPage(), color: Colors.purple),
                    _buildDrawerItem(Icons.psychology, "Rapport global d'analyse IA",AdminNlpReportPage(), color: Colors.purple),

            _buildDrawerItem(Icons.directions_car, "Analyse IA Chauffeurs", const ClientAiDashboardPage(), color: Colors.deepPurple),
            _buildDrawerItem(Icons.account_circle, "Mon Profil", ProfilePage (userEmail: widget.adminEmail)),
            Divider(),
            ExpansionTile(
              leading: const Icon(Icons.language, color: Colors.teal),
              title: Text(AppLocalizations.of(context)!.language),
              children: [
                _buildLanguageItem("Français", 'fr'),
                _buildLanguageItem("English", 'en'),
                _buildLanguageItem("العربية", 'ar'),
              ],
            ),
            Divider(),
            ListTile(
              leading: Icon(Icons.logout, color: Colors.red),
              title: Text(AppLocalizations.of(context)!.logout),
              onTap: () async {
                await CurrentUser.clearSession();
                Navigator.of(context).pushNamedAndRemoveUntil('/login', (route) => false);
              },
            ),
          ],
        ),
      ),
      body: isLoading
          ? Center(child: CircularProgressIndicator(color: Colors.teal))
          : SingleChildScrollView(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text("Tableau de Bord", style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                  SizedBox(height: 20),
                  GridView.count(
                    shrinkWrap: true,
                    physics: NeverScrollableScrollPhysics(),
                    crossAxisCount: 2,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                    childAspectRatio: 1.5,
                    children: [
                      _buildStatCard("Lignes", ligneCount.toString(), Icons.map, Colors.green),
                      _buildStatCard("Chauffeurs", chauffeurCount.toString(), Icons.person, Colors.orange),
                      _buildStatCard("Bus", busCount.toString(), Icons.directions_bus, Colors.blue),
                      _buildStatCard("Incidents", incidentCount.toString(), Icons.warning, Colors.red),
                    ],
                  ),
                  SizedBox(height: 30),
                  Text("Actions Rapides", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  SizedBox(height: 15),
                  
                  // --- زدنا كرت الـ Affectation هنا للوصول السريع ---
                   _buildQuickActionCard(
                    "Gestion des Parcours",
                    "Programmer, modifier ou supprimer...",
                     Icons.add_task,
                    Colors.teal,
                     AdminParcoursListPage(), 
                  ),

                  const SizedBox(height: 12),
                  _buildQuickActionCard(
                    "📊 Rapport d'Analyse IA",
                    "Rapport complet sur la satisfaction client et les chauffeurs",
                    Icons.analytics,
                    Colors.indigoAccent,
                    AdminNlpReportPage(),
                  ),

                  const SizedBox(height: 12),
                  _buildQuickActionCard(
                    "🚗 Dashboard Analyse Chauffeurs",
                    "Avis NLP filtrés : comportement, service, score IA par chauffeur",
                    Icons.psychology,
                    Colors.deepPurple,
                    const ClientAiDashboardPage(),
                  ),

                  const SizedBox(height: 12),
                  _buildQuickActionCard(
                    "📜 Historique des Parcours",
                    "Voir l'historique complet des parcours effectués",
                    Icons.history,
                    Colors.blueGrey,
                    AdminHistoriquePage(),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildLanguageItem(String label, String code) {
    final provider = Provider.of<LanguageProvider>(context, listen: false);
    bool isSelected = provider.locale.languageCode == code;
    return ListTile(
      title: Text(label),
      trailing: isSelected ? const Icon(Icons.check, color: Colors.teal) : null,
      onTap: () {
        provider.changeLanguage(code);
        Navigator.pop(context); // Close drawer
      },
    );
  }

  Widget _buildStatCard(String title, String count, IconData icon, Color color) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 4, spreadRadius: 1)],
        border: Border(left: BorderSide(color: color, width: 5)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 30, color: color),
          SizedBox(width: 10),
          Flexible(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(count, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                Text(title, style: TextStyle(color: Colors.grey[600], fontSize: 12), overflow: TextOverflow.ellipsis),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickActionCard(String title, String sub, IconData icon, Color color, Widget? destination) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: Colors.grey[300]!)),
      child: ListTile(
        leading: CircleAvatar(backgroundColor: color.withOpacity(0.1), child: Icon(icon, color: color)),
        title: Text(title, style: TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Text(sub, style: TextStyle(fontSize: 12)),
        trailing: Icon(Icons.arrow_forward_ios, size: 14),
        onTap: () {
          if (destination != null) {
            Navigator.push(context, MaterialPageRoute(builder: (context) => destination));
          }
        },
      ),
    );
  }
}