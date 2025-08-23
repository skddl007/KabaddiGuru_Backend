#!/usr/bin/env python3
"""
Analytics Tool API Routes
FastAPI routes for match-wise and player-wise summary generation
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import logging

from .analytics_engine import KabaddiAnalyticsEngine

# Initialize router
router = APIRouter(prefix="/analytics", tags=["analytics"])

# Initialize analytics engine
analytics_engine = KabaddiAnalyticsEngine()

# Pydantic models for request/response
class MatchSummaryRequest(BaseModel):
    team1: str
    team2: str
    match_number: int

class PlayerSummaryRequest(BaseModel):
    player_name: str
    match_filter: str = "all"  # "all", "last_5_matches", "last_10_matches", "first_5_matches", "first_10_matches"

class TeamsResponse(BaseModel):
    teams: List[str]
    success: bool

class MatchesResponse(BaseModel):
    matches: List[Dict[str, Any]]
    success: bool

class PlayersResponse(BaseModel):
    players: List[str]
    success: bool

class SummaryResponse(BaseModel):
    summary: Dict[str, Any]
    success: bool
    error: Optional[str] = None

@router.get("/teams", response_model=TeamsResponse)
async def get_all_teams():
    """Get all available teams"""
    try:
        teams = analytics_engine.get_all_teams()
        return TeamsResponse(teams=teams, success=True)
    except Exception as e:
        logging.error(f"Error getting teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/matches/{team1}/{team2}", response_model=MatchesResponse)
async def get_matches_between_teams(team1: str, team2: str):
    """Get all matches between two teams"""
    try:
        matches = analytics_engine.get_matches_between_teams(team1, team2)
        return MatchesResponse(matches=matches, success=True)
    except Exception as e:
        logging.error(f"Error getting matches between teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/players", response_model=PlayersResponse)
async def get_all_players():
    """Get all available players"""
    try:
        players = analytics_engine.get_all_players()
        return PlayersResponse(players=players, success=True)
    except Exception as e:
        logging.error(f"Error getting players: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/players/search", response_model=PlayersResponse)
async def search_players(search_term: str = Query(..., min_length=1)):
    """Search for players by name"""
    try:
        players = analytics_engine.search_players(search_term)
        return PlayersResponse(players=players, success=True)
    except Exception as e:
        logging.error(f"Error searching players: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/match-summary", response_model=SummaryResponse)
async def generate_match_summary(request: MatchSummaryRequest):
    """Generate comprehensive match summary"""
    try:
        summary = analytics_engine.generate_match_summary(
            request.match_number,
            request.team1,
            request.team2
        )
        
        if "error" in summary:
            return SummaryResponse(
                summary={},
                success=False,
                error=summary["error"]
            )
        
        return SummaryResponse(summary=summary, success=True)
    except Exception as e:
        logging.error(f"Error generating match summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/player-summary", response_model=SummaryResponse)
async def generate_player_summary(request: PlayerSummaryRequest):
    """Generate comprehensive player summary"""
    try:
        summary = analytics_engine.generate_player_summary(
            request.player_name,
            request.match_filter
        )
        
        if "error" in summary:
            return SummaryResponse(
                summary={},
                success=False,
                error=summary["error"]
            )
        
        return SummaryResponse(summary=summary, success=True)
    except Exception as e:
        logging.error(f"Error generating player summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/player-performance-summary", response_model=SummaryResponse)
async def generate_player_performance_summary(request: PlayerSummaryRequest):
    """Generate LLM-based natural language player performance summary"""
    try:
        # First get the comprehensive player data
        player_data = analytics_engine.generate_player_summary(
            request.player_name,
            request.match_filter
        )
        
        if "error" in player_data:
            return SummaryResponse(
                summary={},
                success=False,
                error=player_data["error"]
            )
        
        # Extract the LLM summary if available
        llm_summary = player_data.get("llm_summary", "Performance summary not available")
        
        # Create a focused response with the LLM summary
        performance_summary = {
            "player": player_data.get("player"),
            "season": player_data.get("season"),
            "match_selection": player_data.get("match_selection"),
            "performance_summary": llm_summary,
            "match_count": len(player_data.get("matches", [])),
            "total_matches": len(player_data.get("matches", []))
        }
        
        return SummaryResponse(summary=performance_summary, success=True)
    except Exception as e:
        logging.error(f"Error generating player performance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tactical-summary", response_model=SummaryResponse)
async def generate_tactical_match_summary(request: MatchSummaryRequest):
    """Generate tactical match summary for team preparation"""
    try:
        # First get the full match summary
        full_summary = analytics_engine.generate_match_summary(
            request.match_number,
            request.team1,
            request.team2
        )
        
        if "error" in full_summary:
            return SummaryResponse(
                summary={},
                success=False,
                error=full_summary["error"]
            )
        
        # Extract tactical analysis from the full summary
        tactical_summary = {
            "match_info": {
                "match_id": full_summary.get("match_id"),
                "teams": full_summary.get("teams"),
                "score": full_summary.get("score"),
                "season": full_summary.get("season"),
                "venue": full_summary.get("venue")
            },
            "tactical_analysis": full_summary.get("tactical_analysis", "Tactical analysis not available"),
            "top_raiders": full_summary.get("top_raiders", []),
            "top_defenders": full_summary.get("top_defenders", []),
            "critical_points": full_summary.get("critical_points", []),
            "opponent_analysis": full_summary.get("opponent_analysis", {})
        }
        
        return SummaryResponse(summary=tactical_summary, success=True)
    except Exception as e:
        logging.error(f"Error generating tactical match summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check for analytics service"""
    try:
        # Test database connection
        teams = analytics_engine.get_all_teams()
        return {
            "status": "healthy",
            "database_connected": len(teams) > 0,
            "teams_count": len(teams)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
