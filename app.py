<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lucky13 Bot Dashboard</title>
</head>
<body>
    <h1>Lucky13 Bot Dashboard</h1>
    <div id="balance">Balance: Loading...</div>
    <div id="active-trades">Active Trades: Loading...</div>

    <script src="https://cdn.socket.io/4.0.0/socket.io.min.js"></script>
    <script>
        const socket = io();

        socket.on('update_balance', data => {
            document.getElementById('balance').textContent = `Balance: ${data.balance} USDT`;
        });

        socket.on('update_trades', data => {
            const activeTrades = data.trades.map(trade => `<p>${trade.symbol} - Status: ${trade.status} - Profit: ${trade.current_profit}</p>`).join('');
            document.getElementById('active-trades').innerHTML = `Active Trades: <br>${activeTrades}`;
        });
    </script>
</body>
</html>
