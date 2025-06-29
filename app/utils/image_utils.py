# app/utils/image_utils.py - Utilitaires pour la gestion des images
import os
import shutil
from typing import Dict, List
from pathlib import Path

class ImageManager:
    """Gestionnaire pour l'organisation des images"""
    
    PROFILE_DIR = "static/upload/profileImage"
    COVER_DIR = "static/upload/coverImage"
    OLD_UPLOAD_DIR = "static/upload"
    
    @classmethod
    def setup_directories(cls):
        """Crée les dossiers nécessaires"""
        os.makedirs(cls.PROFILE_DIR, exist_ok=True)
        os.makedirs(cls.COVER_DIR, exist_ok=True)
    
    @classmethod
    def get_image_info(cls, file_path: str) -> Dict:
        """Analyse un fichier d'image pour déterminer son type"""
        filename = os.path.basename(file_path)
        
        # Heuristiques pour déterminer le type d'image
        if any(keyword in filename.lower() for keyword in ['avatar', 'profile', 'profil']):
            return {
                'type': 'profile',
                'suggested_dir': cls.PROFILE_DIR,
                'url_prefix': '/static/upload/profileImage/'
            }
        elif any(keyword in filename.lower() for keyword in ['cover', 'couverture', 'banner']):
            return {
                'type': 'cover',
                'suggested_dir': cls.COVER_DIR,
                'url_prefix': '/static/upload/coverImage/'
            }
        else:
            # Par défaut, considérer comme une image de profil
            return {
                'type': 'profile',
                'suggested_dir': cls.PROFILE_DIR,
                'url_prefix': '/static/upload/profileImage/'
            }
    
    @classmethod
    def move_image(cls, source_path: str, image_type: str) -> str:
        """Déplace une image vers le bon dossier"""
        cls.setup_directories()
        
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Fichier source introuvable: {source_path}")
        
        filename = os.path.basename(source_path)
        
        if image_type == 'profile':
            destination_dir = cls.PROFILE_DIR
        elif image_type == 'cover':
            destination_dir = cls.COVER_DIR
        else:
            raise ValueError("Type d'image invalide. Utilisez 'profile' ou 'cover'")
        
        destination_path = os.path.join(destination_dir, filename)
        
        # Éviter de déplacer un fichier sur lui-même
        if os.path.abspath(source_path) == os.path.abspath(destination_path):
            return destination_path
        
        # Gérer les conflits de noms
        counter = 1
        original_name, extension = os.path.splitext(filename)
        while os.path.exists(destination_path):
            new_filename = f"{original_name}_{counter}{extension}"
            destination_path = os.path.join(destination_dir, new_filename)
            counter += 1
        
        shutil.move(source_path, destination_path)
        return destination_path
    
    @classmethod
    def scan_old_uploads(cls) -> List[Dict]:
        """Scanne le dossier upload pour trouver les images à réorganiser"""
        orphaned_images = []
        
        if not os.path.exists(cls.OLD_UPLOAD_DIR):
            return orphaned_images
        
        # Extensions d'images supportées
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        
        for item in os.listdir(cls.OLD_UPLOAD_DIR):
            item_path = os.path.join(cls.OLD_UPLOAD_DIR, item)
            
            # Ignorer les dossiers
            if os.path.isdir(item_path):
                continue
            
            # Vérifier si c'est une image
            _, ext = os.path.splitext(item.lower())
            if ext in image_extensions:
                image_info = cls.get_image_info(item_path)
                orphaned_images.append({
                    'path': item_path,
                    'filename': item,
                    'suggested_type': image_info['type'],
                    'suggested_dir': image_info['suggested_dir']
                })
        
        return orphaned_images
    
    @classmethod
    def cleanup_empty_directories(cls):
        """Supprime les dossiers vides"""
        dirs_to_check = [cls.PROFILE_DIR, cls.COVER_DIR]
        
        for directory in dirs_to_check:
            if os.path.exists(directory):
                try:
                    # Essayer de supprimer si vide
                    os.rmdir(directory)
                    print(f"Dossier vide supprimé: {directory}")
                except OSError:
                    # Le dossier n'est pas vide, c'est normal
                    pass

# Fonction d'aide pour FastAPI
def save_uploaded_file(file_content: bytes, filename: str, image_type: str) -> str:
    """Sauvegarde un fichier uploadé dans le bon dossier"""
    ImageManager.setup_directories()
    
    # Déterminer le dossier de destination
    if image_type == 'profile':
        destination_dir = ImageManager.PROFILE_DIR
        url_prefix = '/static/upload/profileImage/'
    elif image_type == 'cover':
        destination_dir = ImageManager.COVER_DIR
        url_prefix = '/static/upload/coverImage/'
    else:
        raise ValueError("Type d'image invalide")
    
    # Gérer les conflits de noms
    file_path = os.path.join(destination_dir, filename)
    counter = 1
    original_name, extension = os.path.splitext(filename)
    while os.path.exists(file_path):
        new_filename = f"{original_name}_{counter}{extension}"
        file_path = os.path.join(destination_dir, new_filename)
        filename = new_filename
        counter += 1
    
    # Sauvegarder le fichier
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    # Retourner l'URL publique
    return url_prefix + filename