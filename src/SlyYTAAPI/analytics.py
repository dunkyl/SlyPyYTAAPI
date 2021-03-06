from dataclasses import dataclass, asdict
from datetime import date, timedelta
import json, csv
from typing import Any
from SlyAPI import *

def makeFilters(filters: dict[str, Any]) -> str:
    out: list[str] = []
    for key, value in filters.items():
        out.append(F"{key}=={value}")
    return ';'.join(out)

class Dimensions(EnumParam):
    '''
    From https://developers.google.com/youtube/analytics/dimensions
    '''
    Day             = 'day'
    Month           = 'month'
    #Week            = '7DayTotals' # deprecated, valid until April 15, 2020
    Country         = 'country'
    Video           = 'video'
    # ...
    

class Metrics(EnumParam):
    '''
    From https://developers.google.com/youtube/reporting#metrics.
    '''
    #Revenue         = 'estimated_partner_revenue' 
    Views           = 'views'
    #TrafficSource   = 'traffic_source_detail'
    Likes           = 'likes'
    Dislikes        = 'dislikes'
    WatchTime       = 'estimatedMinutesWatched'
    #EstimatedCPM    = 'estimated_cpm'
    SubsGained      = 'subscribersGained'
    SubsLost        = 'subscribersLost'
    # ...

@dataclass
class QueryResult:
    kind: str
    columnHeaders: list[dict[str, str]] # { "name": ..., "columnType": ..., "dataType": ... }
    rows: list[list[Any]]

    def saveJSON(self, path: str):
        with open(path, mode='w', encoding='utf8') as f:
            json.dump(asdict(self), f)

    def saveCSV(self, path: str):
        with open(path, mode='w', newline='', encoding='utf8') as f:
            # UTF-8 BOM for Excel
            f.write('\ufeff')
            writer = csv.writer(f)
            headers = [header['name'] for header in self.columnHeaders]
            writer.writerow(headers)
            writer.writerows(self.rows)

class Scope:
    Analytics       = 'https://www.googleapis.com/auth/yt-analytics.readonly'
    Monetary        = 'https://www.googleapis.com/auth/yt-analytics-monetary.readonly'
    YouTube         = 'https://www.googleapis.com/auth/youtube'
    YouTubePartner  = 'https://www.googleapis.com/auth/youtubepartner'
    YouTubeReadOnly = 'https://www.googleapis.com/auth/youtube.readonly'

class YouTubeAnalytics(WebAPI):
    base_url = 'https://youtubeanalytics.googleapis.com/v2'
    DEFAULT_SCOPES = Scope.Analytics + ' ' + Scope.Monetary + ' ' + Scope.YouTubeReadOnly 

    channel_id: str

    def __init__(self, channel_id: str, app: str | OAuth2, user: str | OAuth2User, scope: str = DEFAULT_SCOPES):
        if isinstance(user, str):
            user = OAuth2User(user)

        if isinstance(app, str):
            auth = OAuth2(app, user)
        else:
            auth = app
            auth.user = user
        super().__init__(auth)
        auth.verify_scope(scope)
        self.channel_id = channel_id

    async def video(self, video_id: str, since: date, metrics: Metrics, dims: Dimensions, end_date: date|None=None) -> QueryResult:
        return await self.query(since, metrics, dims, end_date, {'video': video_id})

    async def query(self, since: date, metrics: Metrics, dims: Dimensions, end_date: date|None=None, filters:dict[str, Any]|None=None) -> QueryResult:
        if end_date is None:
            end_date = date.today()
        if dims == Dimensions.Month: # month requires end date as first day of next month
            end_date = end_date - timedelta(days=end_date.day-1)
        result = await self._reports_query(since, end_date , metrics, dims, filters)
        return QueryResult(**result)

    async def _reports_query(self, start_date: date, end_date: date, metrics: Metrics, dims: Dimensions | None = None, filters: dict[str, Any]|None=None) -> dict[str, Any]:
        params = {
            'startDate': start_date.isoformat(),
            'endDate': end_date.isoformat(),
            'ids': F"channel=={self.channel_id}"
        } | metrics.to_dict()
        if filters:
            params['filters'] = makeFilters(filters)
        if dims:
            params |= dims.to_dict()

        return await self.get_json(F"/reports", params)
    