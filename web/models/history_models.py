"""
Analysis History Data Models

This module defines the data models for storing and managing analysis history records.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid
import re
from enum import Enum


class AnalysisStatus(Enum):
    """Analysis status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MarketType(Enum):
    """Market type enumeration"""
    A_SHARE = "A股"
    HK_STOCK = "港股"
    US_STOCK = "美股"


@dataclass
class AnalysisHistoryRecord:
    """
    Analysis History Record Data Model
    
    This class represents a single analysis record with all necessary metadata
    and validation logic for storing analysis results in the database.
    """
    
    # Core identification
    analysis_id: str = field(default_factory=lambda: f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}")
    stock_symbol: str = ""
    stock_name: str = ""
    market_type: str = MarketType.US_STOCK.value
    
    # Timing information
    analysis_date: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Analysis configuration
    status: str = AnalysisStatus.PENDING.value
    analysis_type: str = "comprehensive"
    analysts_used: List[str] = field(default_factory=list)
    research_depth: int = 3
    
    # LLM configuration
    llm_provider: str = "dashscope"
    llm_model: str = "qwen-plus"
    
    # Performance metrics
    execution_time: float = 0.0
    token_usage: Dict[str, Any] = field(default_factory=dict)
    
    # Analysis results
    raw_results: Dict[str, Any] = field(default_factory=dict)
    formatted_results: Dict[str, Any] = field(default_factory=dict)
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization validation and setup"""
        self.validate()
        self.updated_at = datetime.now()
    
    def validate(self) -> None:
        """
        Validate the analysis record data
        
        Raises:
            ValueError: If any validation fails
        """
        errors = []
        
        # Validate stock symbol
        if not self.stock_symbol or not self.stock_symbol.strip():
            errors.append("Stock symbol cannot be empty")
        elif len(self.stock_symbol.strip()) > 20:
            errors.append("Stock symbol cannot exceed 20 characters")
        else:
            # Validate symbol format based on market type
            symbol = self.stock_symbol.strip().upper()
            if self.market_type == MarketType.A_SHARE.value:
                if not re.match(r'^\d{6}$', symbol):
                    errors.append("A-share symbol must be 6 digits (e.g., 000001)")
            elif self.market_type == MarketType.HK_STOCK.value:
                if not (re.match(r'^\d{4,5}\.HK$', symbol) or re.match(r'^\d{4,5}$', symbol)):
                    errors.append("HK stock symbol must be 4-5 digits with optional .HK suffix (e.g., 0700.HK)")
            elif self.market_type == MarketType.US_STOCK.value:
                if not re.match(r'^[A-Z]{1,5}$', symbol):
                    errors.append("US stock symbol must be 1-5 letters (e.g., AAPL)")
        
        # Validate stock name
        if not self.stock_name or not self.stock_name.strip():
            errors.append("Stock name cannot be empty")
        elif len(self.stock_name.strip()) > 100:
            errors.append("Stock name cannot exceed 100 characters")
        
        # Validate market type
        valid_markets = [market.value for market in MarketType]
        if self.market_type not in valid_markets:
            errors.append(f"Market type must be one of: {', '.join(valid_markets)}")
        
        # Validate status
        valid_statuses = [status.value for status in AnalysisStatus]
        if self.status not in valid_statuses:
            errors.append(f"Status must be one of: {', '.join(valid_statuses)}")
        
        # Validate analysts
        valid_analysts = ['market', 'fundamentals', 'news', 'social']
        if not self.analysts_used:
            errors.append("At least one analyst must be specified")
        else:
            invalid_analysts = [a for a in self.analysts_used if a not in valid_analysts]
            if invalid_analysts:
                errors.append(f"Invalid analysts: {', '.join(invalid_analysts)}. Valid options: {', '.join(valid_analysts)}")
        
        # Validate research depth
        if not isinstance(self.research_depth, int) or self.research_depth < 1 or self.research_depth > 5:
            errors.append("Research depth must be an integer between 1 and 5")
        
        # Validate LLM provider
        valid_providers = ['dashscope', 'deepseek', 'openai', 'google']
        if self.llm_provider not in valid_providers:
            errors.append(f"LLM provider must be one of: {', '.join(valid_providers)}")
        
        # Validate LLM model
        if not self.llm_model or not self.llm_model.strip():
            errors.append("LLM model cannot be empty")
        
        # Validate execution time
        if self.execution_time < 0:
            errors.append("Execution time cannot be negative")
        
        # Validate datetime fields
        if not isinstance(self.analysis_date, datetime):
            errors.append("Analysis date must be a datetime object")
        if not isinstance(self.created_at, datetime):
            errors.append("Created at must be a datetime object")
        if not isinstance(self.updated_at, datetime):
            errors.append("Updated at must be a datetime object")
        
        # Validate token usage structure
        if self.token_usage:
            required_token_fields = ['input_tokens', 'output_tokens', 'total_cost']
            for field_name in required_token_fields:
                if field_name in self.token_usage:
                    value = self.token_usage[field_name]
                    if not isinstance(value, (int, float)) or value < 0:
                        errors.append(f"Token usage {field_name} must be a non-negative number")
        
        if errors:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the record to a dictionary suitable for MongoDB storage
        
        Returns:
            Dict containing all record data with proper serialization
        """
        return {
            'analysis_id': self.analysis_id,
            'stock_symbol': self.stock_symbol,
            'stock_name': self.stock_name,
            'market_type': self.market_type,
            'analysis_date': self.analysis_date,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'status': self.status,
            'analysis_type': self.analysis_type,
            'analysts_used': self.analysts_used,
            'research_depth': self.research_depth,
            'llm_provider': self.llm_provider,
            'llm_model': self.llm_model,
            'execution_time': self.execution_time,
            'token_usage': self.token_usage,
            'raw_results': self.raw_results,
            'formatted_results': self.formatted_results,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisHistoryRecord':
        """
        Create an AnalysisHistoryRecord from a dictionary
        
        Args:
            data: Dictionary containing record data
            
        Returns:
            AnalysisHistoryRecord instance
        """
        # Handle datetime conversion if needed
        datetime_fields = ['analysis_date', 'created_at', 'updated_at']
        for field in datetime_fields:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                except ValueError:
                    # Fallback to current time if parsing fails
                    data[field] = datetime.now()
        
        # Create instance with available data
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def update_status(self, new_status: str) -> None:
        """
        Update the analysis status
        
        Args:
            new_status: New status value
        """
        valid_statuses = [status.value for status in AnalysisStatus]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}. Valid options: {', '.join(valid_statuses)}")
        
        self.status = new_status
        self.updated_at = datetime.now()
    
    def add_results(self, raw_results: Dict[str, Any], formatted_results: Dict[str, Any]) -> None:
        """
        Add analysis results to the record
        
        Args:
            raw_results: Raw analysis results from the analysis engine
            formatted_results: Formatted results for display
        """
        self.raw_results = raw_results or {}
        self.formatted_results = formatted_results or {}
        self.updated_at = datetime.now()
        
        # Update status to completed if results are added
        if raw_results and formatted_results:
            self.status = AnalysisStatus.COMPLETED.value
    
    def add_token_usage(self, input_tokens: int, output_tokens: int, total_cost: float) -> None:
        """
        Add token usage information
        
        Args:
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated
            total_cost: Total cost of the analysis
        """
        self.token_usage = {
            'input_tokens': max(0, input_tokens),
            'output_tokens': max(0, output_tokens),
            'total_tokens': max(0, input_tokens + output_tokens),
            'total_cost': max(0.0, total_cost)
        }
        self.updated_at = datetime.now()
    
    def set_execution_time(self, execution_time: float) -> None:
        """
        Set the execution time for the analysis
        
        Args:
            execution_time: Time taken to complete the analysis in seconds
        """
        self.execution_time = max(0.0, execution_time)
        self.updated_at = datetime.now()
    
    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to the record
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        if not self.metadata:
            self.metadata = {}
        self.metadata[key] = value
        self.updated_at = datetime.now()
    
    def is_completed(self) -> bool:
        """Check if the analysis is completed"""
        return self.status == AnalysisStatus.COMPLETED.value
    
    def is_failed(self) -> bool:
        """Check if the analysis failed"""
        return self.status == AnalysisStatus.FAILED.value
    
    def get_display_name(self) -> str:
        """Get a display-friendly name for the analysis"""
        return f"{self.stock_name} ({self.stock_symbol}) - {self.analysis_date.strftime('%Y-%m-%d')}"
    
    def get_cost_summary(self) -> str:
        """Get a formatted cost summary"""
        if not self.token_usage or 'total_cost' not in self.token_usage:
            return "成本信息不可用"
        
        cost = self.token_usage['total_cost']
        if cost == 0:
            return "免费分析"
        elif cost < 0.01:
            return f"¥{cost:.4f}"
        else:
            return f"¥{cost:.2f}"