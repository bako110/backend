backend/
├── app/
│   ├── _init_.py
│   ├── main.py                      # Point d’entrée API (FastAPI/Django)
│   ├── config.py                   # Configuration générale (BDD, secrets)
│
│   ├── users/
│   │   ├── _init_.py
│   │   ├── models.py               # Utilisateur (id, nom, prénom, avatar, niveau, points, statut en ligne, date inscription)
│   │   ├── schemas.py
│   │   ├── services.py             # Gestion profil, avatar, points, niveau, statut
│   │   └── api.py                  # Routes API utilisateurs
│
│   ├── notifications/
│   │   ├── _init_.py
│   │   ├── models.py               # Notifications (id, user_id, type, message, statut lu/non-lu, lien cible, date)
│   │   ├── schemas.py
│   │   ├── services.py             # Création, envoi, mise à jour notifications
│   │   └── api.py                  # Routes API notifications
│
│   ├── events/
│   │   ├── _init_.py
│   │   ├── models.py               # Événements (id, titre, date, heure, lieu, description, image, organisateur, participants)
│   │   ├── schemas.py
│   │   ├── services.py             # CRUD événements, participants, rappels
│   │   └── api.py                  # Routes API événements
│
│   ├── birthdays/
│   │   ├── _init_.py
│   │   ├── models.py               # Anniversaires liés aux utilisateurs (user_id, date anniversaire)
│   │   ├── schemas.py
│   │   ├── services.py             # Notifications anniversaires, calcul dates
│   │   └── api.py                  # Routes API anniversaires
│
│   ├── activities/
│   │   ├── _init_.py
│   │   ├── models.py               # Activités récentes (user_id, action, cible, date, type)
│   │   ├── schemas.py
│   │   ├── services.py             # Gestion fil activité, ajout logs
│   │   └── api.py                  # Routes API activités
│
│   ├── friends/
│   │   ├── _init_.py
│   │   ├── models.py               # Relations d’amitié (user_id, friend_id, statut : demandé, accepté, bloqué)
│   │   ├── schemas.py
│   │   ├── services.py             # Relations, demandes, suggestions, blocages
│   │   └── api.py                  # Routes API amis
│
│   ├── messages/
│   │   ├── _init_.py
│   │   ├── models.py               # Messages privés (conversation_id, sender_id, receiver_id, contenu, statut lu)
│   │   ├── schemas.py
│   │   ├── services.py             # Envoi, lecture, conversations
│   │   └── api.py                  # Routes API messages
│
│   ├── wishlist/
│   │   ├── _init_.py
│   │   ├── models.py               # Souhaits utilisateur (user_id, item, statut)
│   │   ├── schemas.py
│   │   ├── services.py             # Gestion liste souhaits
│   │   └── api.py                  # Routes API wishlist
│
│   ├── stats/
│   │   ├── _init_.py
│   │   ├── models.py               # Statistiques utilisateur (user_id, nb_amis, nb_events, nb_photos, nb_souhaits)
│   │   ├── schemas.py
│   │   ├── services.py             # Calcul et mise à jour stats
│   │   └── api.py                  # Routes API statistiques
│
│   ├── quick_actions/
│   │   ├── _init_.py
│   │   ├── models.py               # Actions rapides (id, titre, icône, couleur, route)
│   │   ├── schemas.py
│   │   ├── services.py             # Actions rapides dynamiques
│   │   └── api.py                  # Routes API actions rapides
│
│   ├── search_history/
│   │   ├── _init_.py
│   │   ├── models.py               # Historique recherche (user_id, requête, date)
│   │   ├── schemas.py
│   │   ├── services.py             # Recherche utilisateur / événements / activité
│   │   └── api.py                  # Routes API recherche
│
│   ├── devices/
│   │   ├── _init_.py
│   │   ├── models.py               # Appareils utilisateur (user_id, token push, type device)
│   │   ├── schemas.py
│   │   ├── services.py             # Gestion tokens notifications push
│   │   └── api.py                  # Routes API devices
│
│   ├── settings/
│   │   ├── _init_.py
│   │   ├── models.py               # Paramètres utilisateur (notifications, préférences)
│   │   ├── schemas.py
│   │   ├── services.py             # Paramètres et préférences utilisateur
│   │   └── api.py                  # Routes API paramètres utilisateur
│
│   ├── db/
│   │   ├── _init_.py
│   │   ├── session.py              # Connexion et gestion ORM
│   │   ├── migrations/            # Fichiers migrations BDD
│
│   ├── auth/
│   │   ├── _init_.py
│   │   ├── jwt_handler.py          # Gestion JWT / tokens
│   │   ├── two_factor.py           # 2FA
│   │   ├── password.py             # Hash mot de passe / reset
│   │   └── permissions.py  
|       ---api.py                # Routes API authentification 
│
│   ├── utils/
│   │   ├── _init_.py
│   │   ├── email.py                # Envoi emails confirmation / notif
│   │   ├── push_notifications.py  # Push notifications (Firebase, APNS)
│   │   ├── logger.py               # Logger centralisé
│   │   ├── helpers.py              # Fonctions utilitaires génériques
│   │   ├── validators.py           # Validation spécifique
│   │   └── constants.py            # Constantes globales
│
│   ├── tests/
│   │   ├── _init_.py
│   │   └── ...                     # Tests unitaires, d’intégration etc.
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
├── README.md
└── scripts/