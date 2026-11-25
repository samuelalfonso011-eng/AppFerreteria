begin;

set local search_path = public, pg_catalog;

insert into categories (name,slug,headline,art,sort_order) values
('Eléctricas','electricas',null,'drill','1'),
('Manuales','manuales','Kit Herramientas Manuales','wrench','2'),
('Pinturas','pinturas','Pinturas y Acabados','roller','3'),
('Iluminación','iluminacion','Iluminación LED Smart','lamp','4'),
('Seguridad','seguridad','Seguridad Industrial','helmet','5')
on conflict do nothing;

with demo(sku,name,slug,category_slug,price,art,stock,description,specs) as (values
('FP-0001','Taladro Percutor Pro X1','taladro-percutor-pro-x1','electricas',489900,'drill',18,'Motor sin escobillas y batería de 20 V para perforar y atornillar.','Motor sin escobillas
Batería de 20 V y 4 Ah
Mandril de 13 mm
Dos velocidades y función percutor'),
('FP-0002','Sierra Circular M4','sierra-circular-m4','electricas',369900,'saw',9,'Base metálica y empuñadura doble para guiar cortes rectos en madera.','Disco de 185 mm
Profundidad de corte de 65 mm
Base de aluminio con bisel de 0 a 45 grados'),
('FP-0003','Kit de llaves combinadas','kit-de-llaves-combinadas','manuales',89900,'wrench',30,'Llaves de acero con boca abierta y extremo de estrella.','12 piezas de 8 a 19 mm
Acero cromo vanadio
Estuche enrollable'),
('FP-0004','Rodillo de microfibra','rodillo-de-microfibra','pinturas',24900,'roller',45,'Rodillo de pelo corto para aplicar acabados uniformes en superficies lisas.','Ancho de 23 cm
Pelo corto de 9 mm
Mango ergonómico con rosca para extensión'),
('FP-0005','Bombilla LED Smart','bombilla-led-smart','iluminacion',54900,'lamp',4,'Luz regulable para adaptar la iluminación del espacio de trabajo.','10 W equivalentes a 75 W
Rosca E27
Temperatura regulable de 2700 K a 6500 K'),
('FP-0006','Casco de seguridad','casco-de-seguridad','seguridad',39900,'helmet',25,'Casco de obra con ajuste de contorno y visera frontal.','Polietileno de alta densidad
Ajuste de rache
Uso industrial clase E'),
('FP-0007','Llave ajustable de 10 pulgadas','llave-ajustable-10','manuales',42900,'wrench',15,'Llave de apertura regulable.','Acero al cromo vanadio'),
('FP-0008','Reflector LED de exterior','reflector-led-exterior','iluminacion',79900,'lamp',12,'Reflector para espacios exteriores.','30 W')
), added as (
    insert into products (sku,name,slug,category_id,price,art,stock,description,specs,is_featured)
    select d.sku,d.name,d.slug,c.id,d.price,d.art,d.stock,d.description,d.specs,d.sku in ('FP-0001','FP-0002')
    from demo d join categories c on c.slug=d.category_slug
    on conflict do nothing returning id,stock
)
insert into inventory_movements(product_id,movement_type,quantity,previous_stock,new_stock,reason)
select id,'PURCHASE_ENTRY',stock,0,stock,'Inventario inicial de demostración' from added;
update cache_versions set token=md5(gen_random_uuid()::text) where scope='catalog';
commit;
-- Administrador: desde backend, python -m flask --app run create-admin
