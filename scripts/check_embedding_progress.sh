#!/bin/bash
# Check embedding pipeline progress

echo "======================================================================"
echo "EMBEDDING PIPELINE STATUS"
echo "======================================================================"
echo ""

# Check if process is running
if ps aux | grep "backend.cli.embed" | grep -v grep > /dev/null; then
    echo "✅ Status: RUNNING"
    PID=$(ps aux | grep "backend.cli.embed" | grep -v grep | awk '{print $2}' | head -1)
    echo "   Process ID: $PID"
    echo "   Started: $(ps -p $PID -o lstart= 2>/dev/null || echo 'unknown')"
else
    echo "❌ Status: STOPPED"
fi

echo ""
echo "----------------------------------------------------------------------"
echo "DATABASE PROGRESS:"
echo "----------------------------------------------------------------------"

psql langviz -c "
    WITH stats AS (
        SELECT 
            COUNT(*) FILTER (WHERE embedding IS NOT NULL) as done,
            COUNT(*) as total,
            ROUND(100.0 * COUNT(*) FILTER (WHERE embedding IS NOT NULL) / COUNT(*), 2) as percent
        FROM entries
    )
    SELECT 
        done || ' / ' || total || ' entries' as progress,
        percent || '%' as complete,
        CASE 
            WHEN done > 0 THEN 
                ROUND((total - done) / (done / EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) * 60), 1) || ' min'
            ELSE 'calculating...'
        END as eta_approx
    FROM stats, entries
    WHERE embedding IS NOT NULL
    GROUP BY done, total, percent;
"

echo ""
echo "----------------------------------------------------------------------"
echo "RECENT ACTIVITY (last 5 log entries):"
echo "----------------------------------------------------------------------"
tail -5 /Users/griffinstrier/projects/LangViz/embed_pipeline.log | grep -o '"event":"[^"]*"' | sed 's/"event":"//g' | sed 's/"//g' | nl

echo ""
echo "======================================================================"
echo "To monitor live: tail -f /Users/griffinstrier/projects/LangViz/embed_pipeline.log"
echo "To stop: pkill -f backend.cli.embed"
echo "======================================================================"

