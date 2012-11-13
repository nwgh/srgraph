$("#submit").click(function(evt) {
    var params = $('form').serializeArray();
    $("#graph_container").load("/graph", params);
    return false;
});
