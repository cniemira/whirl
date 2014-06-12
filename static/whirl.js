Whirl = (function($){
return {
write_iframe: function(data) {
    $('#content_load').html('Loading...');

    // set the iframe contents
    $('#content').squirt(data.body, 
        // When the iFrame is done loading
        function(duration) {
            // set the completion time
            $('#content_load').html(duration + ' ms');

            // then fire the completion call
            $.ajax({
                url: '/c',
                type: 'GET',
                cache: false,
                async: false,
                crossDomain: false,
                dataType: 'json',
                data: {'psid': data.psid},
                headers: {},
                timeout: 5000,
                error: function(jqXHR, textStatus, errorThrown){
                    console.log('error:' + textStatus);
                    console.log(errorThrown);
                },
                success: function(data, textStatus, jqXHR){
                    console.log('success:' + textStatus);
                    $.each(data, function(i, chunk) {
                        Whirl.write_meta(chunk);
                    });
                }
            });
        },
        {
            timeout: function() {
                console.log('iframe content load timed out!');
                $('#content_load').html('Timed out.');
            },
            timeoutDuration: 10000
        });
    var $raw = $('<pre/>').text(data.body).html();
    $('#content_raw').html('<div>View Source</div><pre>'+$raw+'</pre>');
    $('#content_raw').children(':first-child').on('click', function(){
        $(this).parent().children(':not(:first-child)').toggle();
    });

    // set the content length
    $('#content_load').html(data.body.length + ' bytes');
},

write_meta: function(data) {
    // append the meta data
    var $meta_block = $('<div/>');
    $meta_block.append('<pre>GET '+data.url+'</pre>');

    $.each(data.debug, function(i,j){
        var $meta_line = $('<pre/>').text(j).html();
        $meta_block.append('<pre>'+$meta_line+'</pre>');
    });
    $meta_block.children(':not(:first-child)').hide();
    $meta_block.children(':first-child').on('click', function(){
        $(this).parent().children(':not(:first-child)').toggle();
    });
    $meta_block.addClass('network_io');
    $('#meta').append($meta_block);


    // append the certificate chain
    var $cert_block = $('<div/>');
    $cert_block.append('<pre>'+data.cert_chain.length+' Certificates in chain</pre>');
    $.each(data.cert_chain, function(i,j){
        var $cert_line = $('<pre/>').text(j).html();
        $cert_block.append('<pre>'+$cert_line+'</pre>');
    });
    $cert_block.children(':not(:first-child)').hide();
    $cert_block.children(':first-child').on('click', function(){
        $(this).parent().children(':not(:first-child)').toggle();
    });
    $cert_block.addClass('certificate');
    $('#meta').append($cert_block);
},

run: function() {
    console.log('Whirl running');

    $('#go_button').prop('disabled', true);

    $.ajax({
        url: '/i',
        type: 'GET',
        cache: false,
        async: false,
        crossDomain: false,
        dataType: 'json',
        data: $('.param').serialize(),
        headers: {},
        timeout: 5000,
        error: function(jqXHR, textStatus, errorThrown){
            console.log('error:' + textStatus);
            console.log(errorThrown);
        },
        success: function(data, textStatus, jqXHR){
            console.log('success:' + textStatus);
            $.each(data, function(i, chunk) {
                Whirl.write_meta(chunk);
            });
            Whirl.write_iframe(data[0]);
        }
    });

}
}
})(jQuery);
