# app/utils/mongodb_utils.py
from pydantic import HttpUrl
from datetime import datetime
from bson import ObjectId
from typing import Any, Dict

def convert_pydantic_for_mongodb(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit les types Pydantic pour qu'ils soient compatibles avec MongoDB
    
    Args:
        data: Dictionnaire contenant les données à convertir
        
    Returns:
        Dictionnaire avec les types convertis pour MongoDB
    """
    converted = {}
    
    for key, value in data.items():
        if isinstance(value, HttpUrl):
            # Convertir HttpUrl en string
            converted[key] = str(value)
        elif isinstance(value, datetime):
            # Garder datetime tel quel (MongoDB le supporte)
            converted[key] = value
        elif isinstance(value, ObjectId):
            # Convertir ObjectId en string si nécessaire
            converted[key] = str(value)
        elif isinstance(value, list):
            # Traiter récursivement les listes
            converted[key] = [
                convert_pydantic_for_mongodb({"item": item})["item"]
                if isinstance(item, dict)
                else str(item) if isinstance(item, (HttpUrl, ObjectId))
                else item
                for item in value
            ]
        elif isinstance(value, dict):
            # Traiter récursivement les dictionnaires
            converted[key] = convert_pydantic_for_mongodb(value)
        else:
            # Garder les autres types tels quels
            converted[key] = value
    
    return converted

def prepare_model_for_mongodb(model_instance, exclude_fields: set = None):
    """
    Prépare une instance de modèle Pydantic pour MongoDB
    
    Args:
        model_instance: Instance du modèle Pydantic
        exclude_fields: Champs à exclure (par défaut: {"id"})
        
    Returns:
        Dictionnaire prêt pour MongoDB
    """
    if exclude_fields is None:
        exclude_fields = {"id"}
    
    # Convertir en dictionnaire
    data = model_instance.dict(exclude=exclude_fields)
    
    # Convertir les types pour MongoDB
    return convert_pydantic_for_mongodb(data)

def convert_mongodb_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit un résultat MongoDB pour qu'il soit compatible avec Pydantic
    
    Args:
        result: Résultat de la requête MongoDB
        
    Returns:
        Dictionnaire compatible avec Pydantic
    """
    if not result:
        return result
    
    # Convertir _id en string
    if "_id" in result:
        result["_id"] = str(result["_id"])
    
    return result

# Exemple d'utilisation dans les services:
"""
# Dans create_user_profile:
profile_dict = prepare_model_for_mongodb(profile)

# Dans update_user_profile:
clean_updates = convert_pydantic_for_mongodb(updates)

# Dans get_user_profile_by_email:
result = convert_mongodb_result(data)
"""