#!/usr/bin/env python3
"""
Kabaddi Analytics Engine
Handles match-wise and player-wise summary generation
"""

import json
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
from modules.llm_config import get_llm
from langchain.prompts import PromptTemplate
import os

# Database connection parameters: prefer centralized DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "kabaddi_data")

class KabaddiAnalyticsEngine:
    def __init__(self):
        self.connection_string = (
            DATABASE_URL
            if DATABASE_URL and DATABASE_URL.strip()
            else f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        self.logger = logging.getLogger(__name__)
    
    def get_connection(self):
        """Get database connection"""
        try:
            if DATABASE_URL and DATABASE_URL.strip():
                conn = psycopg2.connect(self.connection_string)
            else:
                conn = psycopg2.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME
                )
            return conn
        except Exception as e:
            self.logger.error(f"Database connection error: {e}")
            raise

    def generate_tactical_match_summary_new(self, match_data: Dict[str, Any]) -> str:
        """Generate a tactical match summary in the exact format specified by the user"""
        try:
            llm = get_llm()
            
            # Import the tactical analysis prompt from prompts module
            from modules.prompts import TACTICAL_MATCH_SUMMARY_PROMPT
            
            # Create prompt template from the tactical analysis prompt
            prompt_template = PromptTemplate.from_template(TACTICAL_MATCH_SUMMARY_PROMPT)
            
            # Format the match data for the prompt
            formatted_data = json.dumps(match_data, indent=2, ensure_ascii=False)
            
            # Generate the summary
            response = llm.invoke(prompt_template.format(match_data=formatted_data))
            
            # Extract the summary text
            summary_text = response.content if hasattr(response, 'content') else str(response)
            
            return summary_text
            
        except Exception as e:
            self.logger.error(f"Error generating tactical match summary: {e}")
            return f"Unable to generate tactical summary due to technical issues. Error: {str(e)}"

    def generate_llm_match_summary(self, match_data: Dict[str, Any]) -> str:
        """Generate a natural language summary of the match using Gemini LLM"""
        try:
            # Use the new tactical summary format
            return self.generate_tactical_match_summary_new(match_data)
        except Exception as e:
            self.logger.error(f"Error generating LLM summary: {e}")
            return f"Unable to generate AI summary due to technical issues. Error: {str(e)}"

    def generate_tactical_match_summary(self, match_data: Dict[str, Any]) -> str:
        """Generate a tactical match summary for team preparation using the enhanced prompt"""
        try:
            # Use the new tactical summary format
            return self.generate_tactical_match_summary_new(match_data)
        except Exception as e:
            self.logger.error(f"Error generating tactical match summary: {e}")
            return f"Unable to generate tactical summary due to technical issues. Error: {str(e)}"

    def generate_llm_player_summary(self, player_data: Dict[str, Any]) -> str:
        """Generate a natural language player performance summary using LLM"""
        try:
            llm = get_llm()
            
            # Import the player performance summary prompt from prompts module
            from modules.prompts import PLAYER_PERFORMANCE_SUMMARY_PROMPT
            
            # Create prompt template from the player performance summary prompt
            prompt_template = PromptTemplate.from_template(PLAYER_PERFORMANCE_SUMMARY_PROMPT)
            
            # Format the player data for the prompt
            formatted_data = json.dumps(player_data, indent=2, ensure_ascii=False)
            
            # Generate the summary
            response = llm.invoke(prompt_template.format(player_data=formatted_data))
            
            # Extract the summary text
            summary_text = response.content if hasattr(response, 'content') else str(response)
            
            return summary_text
            
        except Exception as e:
            self.logger.error(f"Error generating LLM player summary: {e}")
            return f"Unable to generate player performance summary due to technical issues. Error: {str(e)}"

    def extract_clean_player_name(self, full_player_name: str) -> str:
        """Extract clean player name from the full format (e.g., 'Pawan Sherawat_RIN_TT17' -> 'Pawan Sherawat')"""
        if not full_player_name:
            return ""
        # Split by underscore and take the first part (the actual name)
        return full_player_name.split('_')[0] if '_' in full_player_name else full_player_name

    def get_all_teams(self) -> List[str]:
        """Get all unique team names from the database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT DISTINCT "Team_A_Name" as team_name FROM "S_RBR"
            UNION
            SELECT DISTINCT "Team_B_Name" as team_name FROM "S_RBR"
            ORDER BY team_name
            """
            
            cursor.execute(query)
            teams = [row[0] for row in cursor.fetchall() if row[0]]
            
            cursor.close()
            conn.close()
            
            return teams
        except Exception as e:
            self.logger.error(f"Error getting teams: {e}")
            return []
    
    def get_matches_between_teams(self, team1: str, team2: str) -> List[Dict]:
        """Get all matches between two teams"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
            SELECT DISTINCT 
                "Match_Number",
                "Season",
                "Match_City_Venue" as "Venue",
                "Team_A_Name",
                "Team_B_Name",
                "Match_Winner_Team"
            FROM "S_RBR"
            WHERE ("Team_A_Name" = %s AND "Team_B_Name" = %s)
               OR ("Team_A_Name" = %s AND "Team_B_Name" = %s)
            ORDER BY "Match_Number"
            """
            
            cursor.execute(query, (team1, team2, team2, team1))
            matches = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return [dict(match) for match in matches]
        except Exception as e:
            self.logger.error(f"Error getting matches between teams: {e}")
            return []
    
    def get_match_data(self, match_number: int, team1: str, team2: str) -> Dict[str, Any]:
        """Get comprehensive match data for analysis"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get basic match info
            match_query = """
            SELECT DISTINCT 
                "Match_Number",
                "Season",
                "Match_City_Venue" as "Venue",
                "Team_A_Name",
                "Team_B_Name",
                "Match_Winner_Team"
            FROM "S_RBR"
            WHERE "Match_Number" = %s
            AND (("Team_A_Name" = %s AND "Team_B_Name" = %s)
                 OR ("Team_A_Name" = %s AND "Team_B_Name" = %s))
            LIMIT 1
            """
            
            cursor.execute(match_query, (match_number, team1, team2, team2, team1))
            match_info = cursor.fetchone()
            
            if not match_info:
                return {}
            
            # Get all raid data for the match
            raids_query = """
            SELECT * FROM "S_RBR"
            WHERE "Match_Number" = %s
            AND (("Team_A_Name" = %s AND "Team_B_Name" = %s)
                 OR ("Team_A_Name" = %s AND "Team_B_Name" = %s))
            ORDER BY "Unique_Raid_Identifier"
            """
            
            cursor.execute(raids_query, (match_number, team1, team2, team2, team1))
            raids_data = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return {
                "match_info": dict(match_info),
                "raids_data": [dict(raid) for raid in raids_data]
            }
        except Exception as e:
            self.logger.error(f"Error getting match data: {e}")
            return {}
    
    def generate_match_summary(self, match_number: int, team1: str, team2: str) -> Dict[str, Any]:
        """Generate comprehensive match summary with enhanced video content and LLM analysis"""
        try:
            # Get match data using the correct table name and column names
            match_query = """
                SELECT * FROM "S_RBR" 
                WHERE "Match_Number" = %s AND (("Team_A_Name" = %s AND "Team_B_Name" = %s) 
                     OR ("Team_A_Name" = %s AND "Team_B_Name" = %s))
                ORDER BY "Unique_Raid_Identifier"
            """
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(match_query, (match_number, team1, team2, team2, team1))
                    raids_data = cursor.fetchall()
                    
                    if not raids_data:
                        return {"error": f"No match data found for Match {match_number} between {team1} and {team2}"}
                    
                    # Get match info
                    match_info = raids_data[0]
                    total_raids = len(raids_data)
                    
                    # Generate score progression first to get accurate final scores
                    score_progression = []
                    team1_running_score = 0
                    team2_running_score = 0
                    
                    for i, raid in enumerate(raids_data, 1):
                        if raid.get("Attack_Result_Status") == "Successful":
                            if raid.get("Attacking_Team_Code") == team1:
                                team1_running_score += raid.get("Points_Scored_By_Attacker", 0)
                            else:
                                team2_running_score += raid.get("Points_Scored_By_Attacker", 0)
                        
                        if raid.get("Defense_Result_Status") == "Successful":
                            if raid.get("Defending_Team_Code") == team1:
                                team1_running_score += raid.get("Points_Scored_By_Defenders", 0)
                            else:
                                team2_running_score += raid.get("Points_Scored_By_Defenders", 0)
                        
                        score_progression.append({
                            "raid_no": i,
                            "team1": team1_running_score,
                            "team2": team2_running_score
                        })
                    
                    # Get final scores from the last raid in progression
                    if score_progression:
                        team1_score = score_progression[-1]["team1"]
                        team2_score = score_progression[-1]["team2"]
                    else:
                        team1_score = 0
                        team2_score = 0
                    
                    # Calculate statistics using correct column names
                    successful_raids = len([r for r in raids_data if r.get("Attack_Result_Status") == "Successful"])
                    successful_tackles = len([r for r in raids_data if r.get("Defense_Result_Status") == "Successful"])
                    
                    # Identify momentum shifts
                    momentum_shifts = []
                    for i, (prev, curr) in enumerate(zip(score_progression[:-1], score_progression[1:]), 2):
                        prev_leader = "team1" if prev["team1"] > prev["team2"] else "team2" if prev["team2"] > prev["team1"] else None
                        curr_leader = "team1" if curr["team1"] > curr["team2"] else "team2" if curr["team2"] > curr["team1"] else None
                        
                        if prev_leader and curr_leader and prev_leader != curr_leader:
                            momentum_shifts.append({
                                "raid_no": i,
                                "event": f"Lead change to {team1 if curr_leader == 'team1' else team2}"
                            })
                    
                    # Identify critical points (super tackles, bonus points)
                    critical_points = []
                    super_tackle_videos = []
                    bonus_point_videos = []
                    
                    # Helper function to get full team name from team code
                    def get_full_team_name(team_code, match_info):
                        if team_code == match_info.get("Team_A_Name"):
                            return match_info.get("Team_A_Name", team_code)
                        elif team_code == match_info.get("Team_B_Name"):
                            return match_info.get("Team_B_Name", team_code)
                        else:
                            return team_code
                    
                    # Helper function to extract clean player name
                    def extract_player_name(player_name):
                        if not player_name or player_name == "Unknown":
                            return "Unknown"
                        # Remove team codes and position indicators (e.g., _LCNR_TN4)
                        if '_' in player_name:
                            return player_name.split('_')[0]
                        return player_name
                    
                    for i, raid in enumerate(raids_data, 1):
                        # Super tackles
                        if raid.get("Super_Tackle_Opportunity") == 1 and raid.get("Defense_Result_Status") == "Successful":
                            defender_name = extract_player_name(raid.get("Primary_Defender_Name", "Unknown"))
                            team_code = raid.get("Defending_Team_Code", "Unknown")
                            full_team_name = get_full_team_name(team_code, match_info)
                            video_url = raid.get("Raid_Video_URL", "")
                            
                            # Add to critical points (without video URL to avoid duplication)
                            critical_points.append({
                                "raid_no": i,
                                "description": f"Super tackle by {defender_name}",
                                "type": "super_tackle",
                                "player": defender_name,
                                "team": full_team_name,
                                "team_code": team_code
                            })
                            
                            # Add to dedicated video array
                            super_tackle_videos.append({
                                "raid_no": i,
                                "player": defender_name,
                                "team": full_team_name,
                                "team_code": team_code,
                                "video_url": video_url if video_url else "Video not available",
                                "timestamp": f"{raid.get('Unique_Raid_Identifier', 0)}s",
                                "description": f"Super tackle by {defender_name} in raid {i}"
                            })
                        
                        # Bonus points
                        if raid.get("Bonus_Point_Available") == 1 and raid.get("Attack_Result_Status") == "Successful":
                            raider_name = extract_player_name(raid.get("Attacking_Player_Name", "Unknown"))
                            team_code = raid.get("Attacking_Team_Code", "Unknown")
                            full_team_name = get_full_team_name(team_code, match_info)
                            video_url = raid.get("Raid_Video_URL", "")
                            
                            # Add to critical points (without video URL to avoid duplication)
                            critical_points.append({
                                "raid_no": i,
                                "description": f"Bonus point by {raider_name}",
                                "type": "bonus_point",
                                "player": raider_name,
                                "team": full_team_name,
                                "team_code": team_code
                            })
                            
                            # Add to dedicated video array
                            bonus_point_videos.append({
                                "raid_no": i,
                                "player": raider_name,
                                "team": full_team_name,
                                "team_code": team_code,
                                "video_url": video_url if video_url else "Video not available",
                                "timestamp": f"{raid.get('Unique_Raid_Identifier', 0)}s",
                                "description": f"Bonus point by {raider_name} in raid {i}"
                            })
                    
                    # Get raider statistics using correct column names
                    raider_stats = {}
                    for raid in raids_data:
                        raider_name = raid.get("Attacking_Player_Name")
                        if raider_name:
                            if raider_name not in raider_stats:
                                raider_stats[raider_name] = {
                                    "raid_points": 0,
                                    "total_raids": 0,
                                    "successful_raids": 0,
                                    "do_or_die_points": 0,
                                    "super_raid_count": 0,
                                    "bonus_points": 0,
                                    "touch_type_breakdown": {
                                        "running_hand_touch": 0,
                                        "toe_touch": 0,
                                        "kick": 0,
                                        "bonus": 0
                                    }
                                }
                            
                            raider_stats[raider_name]["total_raids"] += 1
                            if raid.get("Attack_Result_Status") == "Successful":
                                raider_stats[raider_name]["successful_raids"] += 1
                                raider_stats[raider_name]["raid_points"] += raid.get("Points_Scored_By_Attacker", 0)
                            
                            if raid.get("Bonus_Point_Available") == 1 and raid.get("Attack_Result_Status") == "Successful":
                                raider_stats[raider_name]["bonus_points"] += 1
                                raider_stats[raider_name]["touch_type_breakdown"]["bonus"] += 1
                            
                            # Add touch type breakdown (simplified)
                            if raid.get("Attack_Techniques_Used"):
                                attack_techniques = raid.get("Attack_Techniques_Used").lower()
                                if "hand" in attack_techniques:
                                    raider_stats[raider_name]["touch_type_breakdown"]["running_hand_touch"] += 1
                                elif "toe" in attack_techniques:
                                    raider_stats[raider_name]["touch_type_breakdown"]["toe_touch"] += 1
                                elif "kick" in attack_techniques:
                                    raider_stats[raider_name]["touch_type_breakdown"]["kick"] += 1
                    
                    # Get defender statistics using correct column names
                    defender_stats = {}
                    for raid in raids_data:
                        defender_name = raid.get("Primary_Defender_Name")
                        if defender_name:
                            if defender_name not in defender_stats:
                                defender_stats[defender_name] = {
                                    "tackle_points": 0,
                                    "total_tackles": 0,
                                    "successful_tackles": 0,
                                    "points_conceded": 0,
                                    "super_tackles": 0,
                                    "tackle_type_breakdown": {
                                        "ankle_hold": 0,
                                        "thigh_hold": 0,
                                        "dive_catch": 0,
                                        "chain_catch": 0,
                                        "block": 0,
                                        "dash": 0
                                    }
                                }
                            
                            defender_stats[defender_name]["total_tackles"] += 1
                            if raid.get("Defense_Result_Status") == "Successful":
                                defender_stats[defender_name]["successful_tackles"] += 1
                                defender_stats[defender_name]["tackle_points"] += raid.get("Points_Scored_By_Defenders", 0)
                            else:
                                defender_stats[defender_name]["points_conceded"] += raid.get("Points_Scored_By_Attacker", 0)
                            
                            if raid.get("Super_Tackle_Opportunity") == 1 and raid.get("Defense_Result_Status") == "Successful":
                                defender_stats[defender_name]["super_tackles"] += 1
                            
                            # Add tackle type breakdown (simplified)
                            if raid.get("Defense_Techniques_Used"):
                                defense_techniques = raid.get("Defense_Techniques_Used").lower()
                                if "ankle" in defense_techniques:
                                    defender_stats[defender_name]["tackle_type_breakdown"]["ankle_hold"] += 1
                                elif "thigh" in defense_techniques:
                                    defender_stats[defender_name]["tackle_type_breakdown"]["thigh_hold"] += 1
                                elif "dive" in defense_techniques:
                                    defender_stats[defender_name]["tackle_type_breakdown"]["dive_catch"] += 1
                                elif "chain" in defense_techniques:
                                    defender_stats[defender_name]["tackle_type_breakdown"]["chain_catch"] += 1
                                elif "block" in defense_techniques:
                                    defender_stats[defender_name]["tackle_type_breakdown"]["block"] += 1
                                elif "dash" in defense_techniques:
                                    defender_stats[defender_name]["tackle_type_breakdown"]["dash"] += 1
                    
                    # Calculate success rates
                    for raider in raider_stats.values():
                        raider["raid_success_rate"] = round((raider["successful_raids"] / raider["total_raids"] * 100), 2) if raider["total_raids"] > 0 else 0
                    
                    for defender in defender_stats.values():
                        defender["tackle_success_rate"] = round((defender["successful_tackles"] / defender["total_tackles"] * 100), 2) if defender["total_tackles"] > 0 else 0
                    
                    # Sort raiders and defenders by points
                    top_raiders = sorted(raider_stats.items(), key=lambda x: x[1]["raid_points"], reverse=True)[:5]
                    top_defenders = sorted(defender_stats.items(), key=lambda x: x[1]["tackle_points"], reverse=True)[:5]
                    
                    # Calculate raid type breakdown
                    raid_types = {"bonus": 0, "touch": 0, "empty": 0}
                    for raid in raids_data:
                        if raid.get("Bonus_Point_Available") == 1 and raid.get("Attack_Result_Status") == "Successful":
                            raid_types["bonus"] += 1
                        elif raid.get("Attack_Result_Status") == "Successful":
                            raid_types["touch"] += 1
                        else:
                            raid_types["empty"] += 1
                    
                    # Convert to percentages
                    for raid_type in raid_types:
                        raid_types[raid_type] = round((raid_types[raid_type] / total_raids * 100), 1)
                    
                    # Calculate tackle type breakdown
                    tackle_types = {"ankle_hold": 0, "thigh_hold": 0, "dive_catch": 0, "chain_catch": 0, "block": 0, "dash": 0}
                    for raid in raids_data:
                        if raid.get("Defense_Result_Status") == "Successful" and raid.get("Defense_Techniques_Used"):
                            defense_techniques = raid.get("Defense_Techniques_Used").lower()
                            if "ankle" in defense_techniques:
                                tackle_types["ankle_hold"] += 1
                            elif "thigh" in defense_techniques:
                                tackle_types["thigh_hold"] += 1
                            elif "dive" in defense_techniques:
                                tackle_types["dive_catch"] += 1
                            elif "chain" in defense_techniques:
                                tackle_types["chain_catch"] += 1
                            elif "block" in defense_techniques:
                                tackle_types["block"] += 1
                            elif "dash" in defense_techniques:
                                tackle_types["dash"] += 1
                    
                    # Generate match highlights
                    match_highlights = [
                        f"{team1 if team1_score > team2_score else team2} won the match with a final score of {team1_score}-{team2_score}",
                        f"Total {total_raids} raids were played in this match",
                        f"Match featured {len(critical_points)} critical moments including super tackles and bonus points"
                    ]
                    
                    if len(super_tackle_videos) > 0:
                        match_highlights.append(f"Match included {len(super_tackle_videos)} spectacular super tackles")
                    
                    if len(bonus_point_videos) > 0:
                        match_highlights.append(f"Match featured {len(bonus_point_videos)} bonus point moments")
                    
                    # Build the enhanced final summary
                    summary = {
                        "match_id": f"Match_{match_number}",
                        "season": match_info.get("Season", "PKL11"),
                        "venue": match_info.get("Match_City_Venue", "13_PlayOffs"),
                        "teams": {
                            "team1": team1,
                            "team2": team2
                        },
                        "score": {
                            "team1": team1_score,
                            "team2": team2_score,
                            "winner": team1 if team1_score > team2_score else team2
                        },
                        "timeline": {
                            "score_progression": score_progression,
                            "momentum_shifts": momentum_shifts,
                            "critical_points": critical_points
                        },
                        "summary": {
                            "total_raids": total_raids,
                            "raid_success_rate": round((successful_raids / total_raids * 100), 2) if total_raids > 0 else 0,
                            "total_tackles": total_raids,
                            "tackle_success_rate": round((successful_tackles / total_raids * 100), 2) if total_raids > 0 else 0,
                            "all_outs_for": 0,  # Would need additional data
                            "all_outs_against": 0,  # Would need additional data
                            "do_or_die_success_rate": 0,  # Would need additional calculation
                            "super_tackles": len(super_tackle_videos),
                            "super_raids": 0  # Not available in current schema
                        },
                        "raid_type_breakdown": raid_types,
                        "tackle_type_breakdown": tackle_types,
                        "top_raiders": [
                            {
                                "name": name,
                                "raid_points": stats["raid_points"],
                                "raid_success_rate": stats["raid_success_rate"],
                                "do_or_die_points": stats["do_or_die_points"],
                                "super_raid_count": stats["super_raid_count"],
                                "touch_type_breakdown": stats["touch_type_breakdown"]
                            }
                            for name, stats in top_raiders
                        ],
                        "top_defenders": [
                            {
                                "name": name,
                                "tackle_points": stats["tackle_points"],
                                "tackle_success_rate": stats["tackle_success_rate"],
                                "points_conceded": stats["points_conceded"],
                                "tackle_type_breakdown": stats["tackle_type_breakdown"]
                            }
                            for name, stats in top_defenders
                        ],
                        "opponent_analysis": {
                            "opponent_strong_zones": [],
                            "opponent_weak_zones": [],
                            "player_vs_player": []
                        },
                        "patterns": [],
                        "match_highlights": match_highlights,
                        "key_raids_video": [],
                        "super_tackle_videos": super_tackle_videos,
                        "bonus_point_videos": bonus_point_videos
                    }
                    
                    # Generate tactical match summary for team preparation
                    try:
                        tactical_summary = self.generate_tactical_match_summary(summary)
                        summary["tactical_analysis"] = tactical_summary
                    except Exception as e:
                        self.logger.error(f"Error generating tactical summary: {e}")
                        summary["tactical_analysis"] = "Tactical analysis temporarily unavailable."
                    
                    return summary
                    
        except Exception as e:
            self.logger.error(f"Error generating match summary: {e}")
            return {"error": str(e)}
    
    def get_all_players(self) -> List[str]:
        """Get all unique player names from the database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT DISTINCT "Attacking_Player_Name" as player_name FROM "S_RBR" WHERE "Attacking_Player_Name" IS NOT NULL
            UNION
            SELECT DISTINCT "Primary_Defender_Name" as player_name FROM "S_RBR" WHERE "Primary_Defender_Name" IS NOT NULL
            UNION
            SELECT DISTINCT "Secondary_Defender_Name" as player_name FROM "S_RBR" WHERE "Secondary_Defender_Name" IS NOT NULL
            ORDER BY player_name
            """
            
            cursor.execute(query)
            full_player_names = [row[0] for row in cursor.fetchall() if row[0]]
            
            # Extract clean player names and remove duplicates
            clean_names = list(set([self.extract_clean_player_name(name) for name in full_player_names]))
            clean_names.sort()
            
            cursor.close()
            conn.close()
            
            return clean_names
        except Exception as e:
            self.logger.error(f"Error getting players: {e}")
            return []
    
    def search_players(self, search_term: str) -> List[str]:
        """Search for players by name"""
        try:
            all_players = self.get_all_players()
            search_term_lower = search_term.lower()
            
            # Filter players that contain the search term
            matching_players = [
                player for player in all_players 
                if search_term_lower in player.lower()
            ]
            
            return matching_players[:10]  # Limit to 10 results
        except Exception as e:
            self.logger.error(f"Error searching players: {e}")
            return []
    
    def get_full_player_name(self, clean_player_name: str) -> str:
        """Get the full player name format from clean name for database queries"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
            SELECT DISTINCT "Attacking_Player_Name" as player_name FROM "S_RBR" 
            WHERE "Attacking_Player_Name" ILIKE %s
            UNION
            SELECT DISTINCT "Primary_Defender_Name" as player_name FROM "S_RBR" 
            WHERE "Primary_Defender_Name" ILIKE %s
            UNION
            SELECT DISTINCT "Secondary_Defender_Name" as player_name FROM "S_RBR" 
            WHERE "Secondary_Defender_Name" ILIKE %s
            LIMIT 1
            """
            
            search_pattern = f"%{clean_player_name}%"
            cursor.execute(query, (search_pattern, search_pattern, search_pattern))
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            return result[0] if result else clean_player_name
        except Exception as e:
            self.logger.error(f"Error getting full player name: {e}")
            return clean_player_name
    
    def get_player_matches(self, player_name: str, match_filter: str = "all") -> List[Dict]:
        """Get matches for a specific player with optional filtering"""
        try:
            # Get the full player name format for database queries
            full_player_name = self.get_full_player_name(player_name)
            
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Base query to get all matches for the player
            base_query = """
            SELECT DISTINCT 
                "Match_Number",
                "Season",
                "Team_A_Name",
                "Team_B_Name",
                "Match_Winner_Team",
                "Attacking_Player_Name",
                "Primary_Defender_Name",
                "Secondary_Defender_Name"
            FROM "S_RBR"
            WHERE "Attacking_Player_Name" ILIKE %s OR "Primary_Defender_Name" ILIKE %s OR "Secondary_Defender_Name" ILIKE %s
            ORDER BY "Match_Number"
            """
            
            search_pattern = f"%{player_name}%"
            cursor.execute(base_query, (search_pattern, search_pattern, search_pattern))
            all_matches = cursor.fetchall()
            
            # Apply filtering
            if match_filter == "last_5_matches":
                all_matches = all_matches[-5:]
            elif match_filter == "last_10_matches":
                all_matches = all_matches[-10:]
            elif match_filter == "first_5_matches":
                all_matches = all_matches[:5]
            elif match_filter == "first_10_matches":
                all_matches = all_matches[:10]
            
            cursor.close()
            conn.close()
            
            return [dict(match) for match in all_matches]
        except Exception as e:
            self.logger.error(f"Error getting player matches: {e}")
            return []
    
    def generate_player_summary(self, player_name: str, match_filter: str = "all") -> Dict[str, Any]:
        """Generate comprehensive player summary"""
        try:
            # Get player matches
            player_matches = self.get_player_matches(player_name, match_filter)
            
            if not player_matches:
                return {"error": "No matches found for this player"}
            
            # Get detailed player data for all matches
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            match_numbers = [match["Match_Number"] for match in player_matches]
            placeholders = ','.join(['%s'] * len(match_numbers))
            
            query = f"""
            SELECT * FROM "S_RBR"
            WHERE "Match_Number" IN ({placeholders})
            AND ("Attacking_Player_Name" ILIKE %s OR "Primary_Defender_Name" ILIKE %s OR "Secondary_Defender_Name" ILIKE %s)
            ORDER BY "Match_Number", "Unique_Raid_Identifier"
            """
            
            search_pattern = f"%{player_name}%"
            cursor.execute(query, match_numbers + [search_pattern, search_pattern, search_pattern])
            player_data = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            # Process player data
            matches_summary = []
            
            for match in player_matches:
                match_number = match["Match_Number"]
                match_raids = [raid for raid in player_data if raid["Match_Number"] == match_number]
                
                # Calculate match statistics
                raid_stats = {
                    "total_raids": len([r for r in match_raids if player_name.lower() in r["Attacking_Player_Name"].lower()]),
                    "successful_raids": len([r for r in match_raids if player_name.lower() in r["Attacking_Player_Name"].lower() and r["Attack_Result_Status"] == "Successful"]),
                    "unsuccessful_raids": len([r for r in match_raids if player_name.lower() in r["Attacking_Player_Name"].lower() and r["Attack_Result_Status"] == "Unsuccessful"]),
                    "empty_raids": len([r for r in match_raids if player_name.lower() in r["Attacking_Player_Name"].lower() and r["Attack_Result_Status"] == "Empty"]),
                    "raid_points": sum([r.get("Points_Scored_By_Attacker", 0) for r in match_raids if player_name.lower() in r["Attacking_Player_Name"].lower()]),
                    "bonus_points": len([r for r in match_raids if player_name.lower() in r["Attacking_Player_Name"].lower() and r.get("Bonus_Point_Available") == 1]),
                    "do_or_die_attempts": len([r for r in match_raids if player_name.lower() in r["Attacking_Player_Name"].lower() and r.get("Do_Or_Die_Mandatory_Raid") == 1]),
                    "do_or_die_success": len([r for r in match_raids if player_name.lower() in r["Attacking_Player_Name"].lower() and r.get("Do_Or_Die_Mandatory_Raid") == 1 and r["Attack_Result_Status"] == "Successful"])
                }
                
                tackle_stats = {
                    "total_tackles": len([r for r in match_raids if (r["Primary_Defender_Name"] and player_name.lower() in r["Primary_Defender_Name"].lower()) or (r["Secondary_Defender_Name"] and player_name.lower() in r["Secondary_Defender_Name"].lower())]),
                    "successful_tackles": len([r for r in match_raids if ((r["Primary_Defender_Name"] and player_name.lower() in r["Primary_Defender_Name"].lower()) or (r["Secondary_Defender_Name"] and player_name.lower() in r["Secondary_Defender_Name"].lower())) and r["Defense_Result_Status"] == "Successful"]),
                    "tackle_points": sum([r.get("Points_Scored_By_Defenders", 0) for r in match_raids if (r["Primary_Defender_Name"] and player_name.lower() in r["Primary_Defender_Name"].lower()) or (r["Secondary_Defender_Name"] and player_name.lower() in r["Secondary_Defender_Name"].lower())]),
                    "super_tackles": len([r for r in match_raids if ((r["Primary_Defender_Name"] and player_name.lower() in r["Primary_Defender_Name"].lower()) or (r["Secondary_Defender_Name"] and player_name.lower() in r["Secondary_Defender_Name"].lower())) and r.get("Super_Tackle_Opportunity") == 1 and r["Defense_Result_Status"] == "Successful"])
                }
                
                # Determine opponent team
                if match["Team_A_Name"] in player_name or any(r["Attacking_Player_Name"] == player_name for r in match_raids):
                    opponent_team = match["Team_B_Name"] if match["Team_A_Name"] in player_name else match["Team_A_Name"]
                else:
                    opponent_team = match["Team_A_Name"] if match["Team_B_Name"] in player_name else match["Team_B_Name"]
                
                # Determine match result
                player_team = match["Team_A_Name"] if match["Team_A_Name"] != opponent_team else match["Team_B_Name"]
                match_status = "Win" if match["Match_Winner_Team"] == player_team else "Loss"
                
                # Get final scores
                final_scores = {"team": 0, "opponent": 0}
                
                # Check for achievements
                achievements = {
                    "super_10": raid_stats["raid_points"] >= 10,
                    "high_5": tackle_stats["tackle_points"] >= 5,
                    "milestones": []
                }
                
                if raid_stats["raid_points"] >= 10:
                    achievements["milestones"].append("Super 10 achievement")
                if tackle_stats["tackle_points"] >= 5:
                    achievements["milestones"].append("High 5 achievement")
                
                # Get highlights
                highlights = {
                    "key_raids": [],
                    "super_tackle_clips": [],
                    "match_turning_points": []
                }
                
                # Add key raids
                for raid in match_raids:
                    if player_name.lower() in raid["Attacking_Player_Name"].lower() and raid.get("Points_Scored_By_Attacker", 0) > 0:
                        highlights["key_raids"].append({
                            "description": f"{raid.get('Points_Scored_By_Attacker', 0)}-point raid",
                            "video_url": raid.get("Raid_Video_URL", "")
                        })
                    
                    if ((raid["Primary_Defender_Name"] and player_name.lower() in raid["Primary_Defender_Name"].lower()) or (raid["Secondary_Defender_Name"] and player_name.lower() in raid["Secondary_Defender_Name"].lower())) and raid.get("Super_Tackle_Opportunity") == 1:
                        highlights["super_tackle_clips"].append({
                            "description": "Super tackle",
                            "video_url": raid.get("Raid_Video_URL", "")
                        })
                
                matches_summary.append({
                    "match_number": match_number,
                    "opponent_team": opponent_team,
                    "result": {
                        "status": match_status,
                        "final_score": final_scores
                    },
                    "raid_stats": raid_stats,
                    "tackle_stats": tackle_stats,
                    "achievements": achievements,
                    "highlights": highlights
                })
            
            # Build the final player summary
            player_summary = {
                "player": player_name,
                "season": player_matches[0]["Season"] if player_matches else "Unknown",
                "match_selection": match_filter,
                "matches": matches_summary
            }
            
            # Generate LLM-based natural language summary
            try:
                llm_summary = self.generate_llm_player_summary(player_summary)
                player_summary["llm_summary"] = llm_summary
            except Exception as e:
                self.logger.error(f"Error generating LLM summary for player {player_name}: {e}")
                player_summary["llm_summary"] = "Unable to generate performance summary at this time."
            
            return player_summary
            
        except Exception as e:
            self.logger.error(f"Error generating player summary: {e}")
            return {"error": str(e)}
