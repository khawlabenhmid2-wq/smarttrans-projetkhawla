import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../api_config.dart';


class ClientAiDashboardPage extends StatefulWidget {
  const ClientAiDashboardPage({super.key});

  @override
  State<ClientAiDashboardPage> createState() => _ClientAiDashboardPageState();
}

class _ClientAiDashboardPageState extends State<ClientAiDashboardPage> {
  Map<String, dynamic> driverReport = {};
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => isLoading = true);
    try {
      // 1. Re-catégoriser tous les avis avec NLP amélioré
      await http.post(Uri.parse('${ApiConfig.baseUrl}/recategorize_avis'));


      // 2. Récupérer le rapport chauffeur
      final resp = await http
          .get(Uri.parse('${ApiConfig.baseUrl}/get_driver_nlp_report'));

      if (resp.statusCode == 200) {
        driverReport = json.decode(resp.body);
      }
    } catch (e) {
      debugPrint('Erreur chargement données IA: $e');
    }
    setState(() => isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F6FB),
      appBar: AppBar(
        title: const Text(
          'Analyse IA — Chauffeurs',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        flexibleSpace: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [Color(0xFF6A11CB), Color(0xFF2575FC)],
            ),
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: _loadData,
            tooltip: 'Actualiser',
          ),
        ],
      ),
      body: isLoading ? _buildLoader() : _buildDriverDashboard(),
    );
  }

  Widget _buildLoader() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                    color: Colors.black.withOpacity(0.08),
                    blurRadius: 20,
                    spreadRadius: 2)
              ],
            ),
            child: Column(
              children: [
                const CircularProgressIndicator(
                    color: Color(0xFF6A11CB), strokeWidth: 3),
                const SizedBox(height: 16),
                const Text(
                  '🤖 NLP en cours d\'analyse...',
                  style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF6A11CB)),
                ),
                const SizedBox(height: 4),
                Text(
                  'Catégorisation des commentaires chauffeurs',
                  style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════════
  //  DASHBOARD ANALYSE CHAUFFEURS
  // ═══════════════════════════════════════════════════════
  Widget _buildDriverDashboard() {
    final int total = driverReport['total_avis_chauffeur'] ?? 0;

    if (total == 0) {
      return _buildEmptyState();
    }

    final double satisfaction =
        (driverReport['satisfaction_chauffeur'] ?? 0.0).toDouble();
    final double avgNote = (driverReport['avg_note'] ?? 0.0).toDouble();
    final Map sentDist = driverReport['sentiment_distribution'] as Map? ?? {};
    final List keywords = driverReport['top_keywords'] as List? ?? [];
    final List topDrivers = driverReport['top_drivers'] as List? ?? [];
    final List avisList = driverReport['avis_list'] as List? ?? [];

    int pos = (sentDist['Positif'] ?? 0) as int;
    int neg = (sentDist['Négatif'] ?? 0) as int;
    int neu = (sentDist['Neutre'] ?? 0) as int;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Bannière NLP ──────────────────────────────
          _buildNlpBanner(total),
          const SizedBox(height: 16),

          // ── Score global ──────────────────────────────
          _buildScoreCard(satisfaction, avgNote),
          const SizedBox(height: 16),

          // ── Sentiment Distribution ────────────────────
          _sectionTitle('Distribution des Sentiments', Icons.mood),
          const SizedBox(height: 10),
          _buildSentimentBars(pos, neg, neu, total),
          const SizedBox(height: 20),

          // ── Mots-clés IA ──────────────────────────────
          if (keywords.isNotEmpty) ...[
            _sectionTitle('Mots-clés Chauffeur Détectés', Icons.label_important),
            const SizedBox(height: 10),
            _buildKeywordCloud(keywords),
            const SizedBox(height: 20),
          ],

          // ── Top Chauffeurs ────────────────────────────
          if (topDrivers.isNotEmpty) ...[
            _sectionTitle('Évaluation des Chauffeurs (IA)', Icons.emoji_events),
            const SizedBox(height: 10),
            _buildTopDriversCards(topDrivers),
            const SizedBox(height: 20),
          ],

          // ── Liste des avis chauffeur ──────────────────
          _sectionTitle('Avis détectés — Chauffeurs ($total)', Icons.comment),
          const SizedBox(height: 10),
          ...avisList.map((a) => _buildAvisCard(a)),
        ],
      ),
    );
  }

  Widget _buildNlpBanner(int count) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
            colors: [Color(0xFF6A11CB), Color(0xFF2575FC)]),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
              color: const Color(0xFF6A11CB).withOpacity(0.3),
              blurRadius: 14,
              offset: const Offset(0, 5)),
        ],
      ),
      child: Row(
        children: [
          const Text('🤖', style: TextStyle(fontSize: 32)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'NLP a analysé les commentaires',
                  style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 14),
                ),
                Text(
                  '$count commentaire(s) concernent les chauffeurs',
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ],
            ),
          ),
          Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              '$count avis',
              style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildScoreCard(double satisfaction, double avgNote) {
    Color scoreColor = satisfaction >= 60
        ? Colors.green
        : satisfaction >= 40
            ? Colors.orange
            : Colors.red;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withOpacity(0.07),
              blurRadius: 15,
              spreadRadius: 2)
        ],
      ),
      child: Row(
        children: [
          // Score IA
          Expanded(
            child: Column(
              children: [
                Text(
                  '${satisfaction.toStringAsFixed(1)}%',
                  style: TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.bold,
                      color: scoreColor),
                ),
                const SizedBox(height: 4),
                const Text('Score IA Satisfaction',
                    style: TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: LinearProgressIndicator(
                    value: satisfaction / 100,
                    backgroundColor: Colors.grey[200],
                    valueColor: AlwaysStoppedAnimation<Color>(scoreColor),
                    minHeight: 8,
                  ),
                ),
              ],
            ),
          ),
          Container(
            width: 1,
            height: 80,
            color: Colors.grey[200],
            margin: const EdgeInsets.symmetric(horizontal: 20),
          ),
          // Note moyenne
          Expanded(
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.star, color: Colors.amber, size: 32),
                    const SizedBox(width: 4),
                    Text(
                      avgNote.toStringAsFixed(1),
                      style: const TextStyle(
                          fontSize: 36,
                          fontWeight: FontWeight.bold,
                          color: Colors.amber),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                const Text('Note Moyenne /5',
                    style: TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(
                    5,
                    (i) => Icon(
                      i < avgNote.round() ? Icons.star : Icons.star_border,
                      color: Colors.amber,
                      size: 18,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSentimentBars(int pos, int neg, int neu, int total) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withOpacity(0.06),
              blurRadius: 12,
              spreadRadius: 1)
        ],
      ),
      child: Column(
        children: [
          _sentimentBar('😊 Positif', pos, total, Colors.green),
          const SizedBox(height: 12),
          _sentimentBar('😐 Neutre', neu, total, Colors.orange),
          const SizedBox(height: 12),
          _sentimentBar('😞 Négatif', neg, total, Colors.red),
        ],
      ),
    );
  }

  Widget _sentimentBar(String label, int count, int total, Color color) {
    double pct = total > 0 ? count / total : 0;
    return Row(
      children: [
        SizedBox(
          width: 90,
          child: Text(label, style: const TextStyle(fontSize: 13)),
        ),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(
              value: pct,
              backgroundColor: color.withOpacity(0.1),
              valueColor: AlwaysStoppedAnimation<Color>(color),
              minHeight: 16,
            ),
          ),
        ),
        const SizedBox(width: 10),
        Text(
          '$count (${(pct * 100).toStringAsFixed(0)}%)',
          style: TextStyle(
              fontWeight: FontWeight.bold, color: color, fontSize: 12),
        ),
      ],
    );
  }

  Widget _buildKeywordCloud(List keywords) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: keywords.map<Widget>((kw) {
        final word = kw[0] as String;
        final count = kw[1] as int;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
                colors: [Color(0xFF6A11CB), Color(0xFF2575FC)]),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            '$word ($count)',
            style: const TextStyle(color: Colors.white, fontSize: 12),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildTopDriversCards(List drivers) {
    final medals = ['🥇', '🥈', '🥉'];
    return Column(
      children: drivers.asMap().entries.map((entry) {
        final d = entry.value as Map;
        final score =
            (((d['avg_sentiment'] ?? 0) as num).toDouble() + 1) / 2 * 100;
        final nbAvis = d['nb_avis'] ?? 0;
        final Color c = score >= 60
            ? Colors.green
            : score >= 40
                ? Colors.orange
                : Colors.red;

        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(14),
            boxShadow: [
              BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 10,
                  spreadRadius: 1)
            ],
          ),
          child: Row(
            children: [
              Text(
                entry.key < 3 ? medals[entry.key] : '👤',
                style: const TextStyle(fontSize: 26),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      d['Nom'] ?? 'Inconnu',
                      style: const TextStyle(
                          fontWeight: FontWeight.bold, fontSize: 15),
                    ),
                    Text('$nbAvis avis reçus',
                        style: const TextStyle(
                            color: Colors.grey, fontSize: 11)),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '${score.toStringAsFixed(1)}%',
                    style: TextStyle(
                        color: c,
                        fontWeight: FontWeight.bold,
                        fontSize: 18),
                  ),
                  Text('Score IA',
                      style:
                          TextStyle(color: c.withOpacity(0.7), fontSize: 10)),
                ],
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildAvisCard(dynamic avis) {
    final String sentiment = avis['Sentiment_label'] ?? 'Neutre';
    final Color sColor = sentiment == 'Positif'
        ? Colors.green
        : sentiment == 'Négatif'
            ? Colors.red
            : Colors.orange;
    final IconData sIcon = sentiment == 'Positif'
        ? Icons.sentiment_very_satisfied
        : sentiment == 'Négatif'
            ? Icons.sentiment_very_dissatisfied
            : Icons.sentiment_neutral;
    final double sentScore =
        (avis['Sentiment_score'] ?? 0.0).toDouble();
    final double scoreDisplay = (sentScore + 1) / 2 * 100;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withOpacity(0.05),
              blurRadius: 10,
              spreadRadius: 1)
        ],
        border: Border(left: BorderSide(color: sColor, width: 4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: sColor.withOpacity(0.12),
                child: Icon(sIcon, color: sColor, size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  avis['Commentaire'] ?? '...',
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 14),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              _badge(sentiment, sColor),
              _badge('⭐ ${avis['Note']}/5', Colors.amber),
              _badge('🤖 IA: ${scoreDisplay.toStringAsFixed(0)}%',
                  const Color(0xFF6A11CB)),
              if (avis['Nom_Client'] != null)
                _badge('👤 ${avis['Nom_Client']}', Colors.blueGrey),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              const Text('Score IA: ',
                  style: TextStyle(fontSize: 11, color: Colors.grey)),
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: LinearProgressIndicator(
                    value: scoreDisplay / 100,
                    backgroundColor: Colors.grey[100],
                    valueColor: AlwaysStoppedAnimation<Color>(sColor),
                    minHeight: 6,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '${scoreDisplay.toStringAsFixed(1)}%',
                style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: sColor),
              ),
            ],
          ),
          if (avis['Keywords'] != null &&
              (avis['Keywords'] as String).isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              '🔑 Mots-clés: ${avis['Keywords']}',
              style: TextStyle(
                  fontSize: 11,
                  fontStyle: FontStyle.italic,
                  color: Colors.indigo[400]),
            ),
          ],
        ],
      ),
    );
  }

  Widget _badge(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        style: TextStyle(
            fontSize: 11, color: color, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _sectionTitle(String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, color: const Color(0xFF6A11CB), size: 20),
        const SizedBox(width: 8),
        Text(
          title,
          style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.bold,
              color: Color(0xFF1A1A2E)),
        ),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.orange.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.person_off, size: 60, color: Colors.orange),
            ),
            const SizedBox(height: 20),
            const Text(
              'Aucun commentaire chauffeur détecté',
              style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Colors.orange),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 10),
            Text(
              'Le NLP n\'a trouvé aucun avis mentionnant le comportement ou le service des chauffeurs.',
              style: TextStyle(color: Colors.grey[500], fontSize: 13),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
